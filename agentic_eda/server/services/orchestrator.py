"""The server's own four-stage orchestration.

Deliberately a sibling of `agentic_eda.pipeline.run_pipeline` rather than a
refactor of it: the CLI wants prints and flat output paths, the server wants
structured events and per-run isolation. Sharing one function would have meant
bending both. What *is* shared is everything that matters — the same four agent
entrypoints, the same executors, the same profiler.

This module runs entirely on a worker thread. It never touches the event hub
directly; it is handed a threadsafe `emit` callable and calls that. Each stage
gets a small adapter that translates the agents' short `(name, payload)` hook
vocabulary into stamped `EventEnvelope`s.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agentic_eda.data_prep.agent import run_data_prep
from agentic_eda.multivariate_analysis.agent import run_multivariate_analysis
from agentic_eda.report.agent import collect_context, run_report
from agentic_eda.univariate_analysis.agent import run_univariate_analysis

from agentic_eda.server.models.events import (
    AGENT_EVENT_TYPES,
    STAGE_EXPECTED_SECONDS,
    STAGE_LABELS,
    STAGE_ORDER,
    EventType,
    StageId,
)
from agentic_eda.server.services.storage import RunPaths, artifact_url
from agentic_eda.server.settings import settings

logger = logging.getLogger(__name__)

#: `emit(event_type, payload, stage)` — threadsafe, provided by the run manager.
EmitFn = Callable[[EventType, dict[str, Any], StageId | None], None]


class RunCancelled(Exception):
    """Raised between stages when a cancellation has been requested."""


@dataclass
class StageOutcome:
    """What a stage produced, for the orchestrator's own bookkeeping."""

    summary: str | None = None
    artifacts: list[Path] = field(default_factory=list)


def _truncate(text: str) -> str:
    limit = settings.max_error_chars
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


class Orchestrator:
    """Runs the four stages for one run, emitting events throughout."""

    def __init__(
        self,
        run_id: str,
        dataset_path: Path,
        paths: RunPaths,
        emit: EmitFn,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self.run_id = run_id
        self.dataset_path = Path(dataset_path)
        self.dataset_name = self.dataset_path.stem
        self.paths = paths
        self._emit = emit
        self._should_cancel = should_cancel or (lambda: False)
        self._stage_started_at: dict[StageId, float] = {}
        self._stage_summaries: dict[StageId, str] = {}
        self._stage_artifacts: dict[StageId, list[Path]] = {}

    # -- emission helpers --------------------------------------------------- #

    def _publish(
        self,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        stage: StageId | None = None,
    ) -> None:
        self._emit(event_type, payload or {}, stage)

    def _stage_hook(self, stage: StageId) -> Callable[[str, dict[str, Any]], None]:
        """Build the `on_event` callable handed to an agent.

        Translates the agent's short event names into wire types, resolves
        artifact paths to URLs, and intercepts `summary` so it can be attached to
        the stage's own `stage.completed` event instead of becoming a bare event.
        """

        def hook(name: str, payload: dict[str, Any]) -> None:
            if name == "summary":
                summary = payload.get("summary")
                if summary:
                    self._stage_summaries[stage] = summary
                return

            if name == "artifact":
                self._publish_artifact(stage, payload)
                return

            event_type = AGENT_EVENT_TYPES.get(name)
            if event_type is None:
                logger.debug("run %s: unmapped agent event %r", self.run_id, name)
                return

            body = dict(payload)
            if name == "retry_exhausted":
                body["exhausted"] = True
            if "error" in body and isinstance(body["error"], str):
                body["error"] = _truncate(body["error"])

            self._publish(event_type, body, stage)

        return hook

    def _publish_artifact(self, stage: StageId, payload: dict[str, Any]) -> None:
        raw_path = payload.get("path")
        if not raw_path:
            return

        path = Path(raw_path)
        url = artifact_url(path)
        if url is None:
            # Outside the served root (e.g. an agent fell back to a flat default
            # path). Record it but do not advertise an unreachable URL.
            logger.warning("run %s: artifact outside RUNS_DIR: %s", self.run_id, path)
            return

        try:
            size = path.stat().st_size
        except OSError:
            size = None

        self._stage_artifacts.setdefault(stage, []).append(path)
        self._publish(
            EventType.ARTIFACT_CREATED,
            {
                "kind": payload.get("kind", "chart"),
                "filename": path.name,
                "url": url,
                "bytes": size,
            },
            stage,
        )

    # -- stage lifecycle ---------------------------------------------------- #

    def _begin_stage(self, stage: StageId) -> None:
        if self._should_cancel():
            raise RunCancelled(f"cancelled before {stage.value}")
        self._stage_started_at[stage] = time.monotonic()
        self._publish(
            EventType.STAGE_STARTED,
            {
                "stage": stage.value,
                "label": STAGE_LABELS[stage],
                "expected_seconds": STAGE_EXPECTED_SECONDS[stage],
            },
            stage,
        )

    def _end_stage(self, stage: StageId) -> None:
        started = self._stage_started_at.get(stage, time.monotonic())
        artifacts = self._stage_artifacts.get(stage, [])
        self._publish(
            EventType.STAGE_COMPLETED,
            {
                "stage": stage.value,
                "summary": self._stage_summaries.get(stage),
                "duration_seconds": round(time.monotonic() - started, 2),
                "artifact_count": len(artifacts),
            },
            stage,
        )

    def _fail_stage(self, stage: StageId, exc: BaseException) -> None:
        started = self._stage_started_at.get(stage, time.monotonic())
        self._publish(
            EventType.STAGE_FAILED,
            {
                "stage": stage.value,
                "error": _truncate(f"{type(exc).__name__}: {exc}"),
                "duration_seconds": round(time.monotonic() - started, 2),
            },
            stage,
        )

    # -- the run ------------------------------------------------------------ #

    def execute(self) -> Path:
        """Run all four stages. Returns the report path; raises on failure."""
        run_started = time.monotonic()

        self._publish(
            EventType.RUN_STARTED,
            {
                "run_id": self.run_id,
                "dataset_name": self.dataset_name,
                "dataset_file": self.dataset_path.name,
                "mode": "live",
                "stages": [
                    {
                        "id": stage.value,
                        "label": STAGE_LABELS[stage],
                        "expected_seconds": STAGE_EXPECTED_SECONDS[stage],
                    }
                    for stage in STAGE_ORDER
                ],
            },
        )

        current_stage: StageId | None = None
        try:
            # --- Stage 1: data preparation --------------------------------- #
            current_stage = StageId.DATA_PREP
            self._begin_stage(current_stage)
            prep_result, cleaned_path = run_data_prep(
                self.dataset_path,
                output_csv_path=self.paths.cleaned_csv_path(self.dataset_name),
                on_event=self._stage_hook(current_stage),
            )
            self._end_stage(current_stage)

            # --- Stage 2a: univariate -------------------------------------- #
            current_stage = StageId.UNIVARIATE
            self._begin_stage(current_stage)
            univariate_result, univariate_charts = run_univariate_analysis(
                cleaned_path,
                charts_dir=self.paths.univariate_charts_dir,
                on_event=self._stage_hook(current_stage),
            )
            self._end_stage(current_stage)

            # --- Stage 2b: multivariate ------------------------------------ #
            current_stage = StageId.MULTIVARIATE
            self._begin_stage(current_stage)
            multivariate_result, multivariate_charts = run_multivariate_analysis(
                cleaned_path,
                charts_dir=self.paths.multivariate_charts_dir,
                on_event=self._stage_hook(current_stage),
            )
            self._end_stage(current_stage)

            # --- Stage 3: report synthesis --------------------------------- #
            current_stage = StageId.REPORT
            self._begin_stage(current_stage)
            report_hook = self._stage_hook(current_stage)
            report_hook("progress", {"message": "aggregating stage context"})
            context = collect_context(
                dataset_name=self.dataset_name,
                cleaned_csv_path=cleaned_path,
                data_prep=prep_result,
                univariate=univariate_result,
                univariate_charts=univariate_charts,
                multivariate=multivariate_result,
                multivariate_charts=multivariate_charts,
            )
            report_path = run_report(
                context,
                output_path=self.paths.report_path(self.dataset_name),
                on_event=report_hook,
            )
            self._end_stage(current_stage)

            chart_count = len(univariate_charts) + len(multivariate_charts)
            self._publish(
                EventType.RUN_COMPLETED,
                {
                    "report_url": artifact_url(report_path),
                    "report_filename": report_path.name,
                    "duration_seconds": round(time.monotonic() - run_started, 2),
                    "chart_count": chart_count,
                },
            )
            return report_path

        except RunCancelled as exc:
            self._publish(
                EventType.RUN_FAILED,
                {
                    "stage": current_stage.value if current_stage else None,
                    "error": str(exc),
                    "cancelled": True,
                    "duration_seconds": round(time.monotonic() - run_started, 2),
                },
            )
            raise

        except BaseException as exc:
            if current_stage is not None:
                self._fail_stage(current_stage, exc)
            logger.exception("run %s failed during %s", self.run_id, current_stage)
            self._publish(
                EventType.RUN_FAILED,
                {
                    "stage": current_stage.value if current_stage else None,
                    "error": _truncate(f"{type(exc).__name__}: {exc}"),
                    "duration_seconds": round(time.monotonic() - run_started, 2),
                },
            )
            raise
