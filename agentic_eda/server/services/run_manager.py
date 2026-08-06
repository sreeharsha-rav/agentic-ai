"""Run registry, lifecycle, and the sync-to-async bridge.

The bridge is the interesting part. Every agent in this project is fully
blocking: `client.responses.parse`, `subprocess.run`, and multi-second
`pd.read_csv` calls. Running any of it on the event loop would freeze the server
for minutes. So:

    POST /api/runs
        -> allocate run + directories
        -> capture the running loop
        -> submit Orchestrator.execute to a ThreadPoolExecutor
        -> return 202 immediately

    worker thread: emit(...) -> loop.call_soon_threadsafe(hub.publish, ...)

Because the worker lives in the executor rather than in a request task, a client
disconnect does **not** cancel the run — which is deliberate: a run costs real
money and several minutes, so it must survive a closed tab. Clients reattach with
`Last-Event-ID` and replay whatever they missed.

State is in memory, mirrored to `run.json` and `events.jsonl` so a completed run
stays inspectable across a restart.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_eda.config import RUNS_DIR

from agentic_eda.server.models.events import (
    STAGE_EXPECTED_SECONDS,
    STAGE_LABELS,
    STAGE_ORDER,
    EventEnvelope,
    EventType,
    RunMode,
    RunStatus,
    StageId,
    StageStatus,
)
from agentic_eda.server.models.schemas import (
    ArtifactInfo,
    ReasoningStepInfo,
    RetryInfo,
    RunSnapshot,
    RunSummary,
    StageSnapshot,
)
from agentic_eda.server.services import storage
from agentic_eda.server.services.event_hub import EventHub, read_events_file
from agentic_eda.server.services.orchestrator import Orchestrator, RunCancelled
from agentic_eda.server.services.replay import replay_events
from agentic_eda.server.settings import settings

logger = logging.getLogger(__name__)


class RunNotFoundError(LookupError):
    pass


class RunCapacityError(RuntimeError):
    """Too many runs already in flight."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Run:
    """One run's server-side state.

    Holds both the raw event hub and a projected `StageSnapshot` per stage. The
    projection exists so `GET /api/runs/{id}` can rehydrate a page reload in one
    request instead of making the client replay hundreds of events.
    """

    def __init__(
        self,
        run_id: str,
        dataset_name: str,
        dataset_id: str | None,
        paths: storage.RunPaths,
        mode: RunMode = RunMode.LIVE,
        replay_of: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.dataset_name = dataset_name
        self.dataset_id = dataset_id
        self.paths = paths
        self.mode = mode
        self.replay_of = replay_of

        self.status = RunStatus.PENDING
        self.created_at = _utc_now()
        self.completed_at: str | None = None
        self.duration_seconds: float | None = None
        self.error: str | None = None
        self.report_url: str | None = None
        self.cancel_requested = False

        self._started_monotonic = time.monotonic()
        self.hub = EventHub(run_id, events_path=paths.events_path)
        self.stages: dict[StageId, StageSnapshot] = {
            stage: StageSnapshot(
                id=stage,
                label=STAGE_LABELS[stage],
                status=StageStatus.PENDING,
                expected_seconds=STAGE_EXPECTED_SECONDS[stage],
            )
            for stage in STAGE_ORDER
        }

    # -- projection --------------------------------------------------------- #

    def apply(self, event: EventEnvelope) -> None:
        """Fold an event into the projected snapshot."""
        stage = self.stages.get(event.stage) if event.stage else None
        payload = event.payload

        match event.type:
            case EventType.RUN_STARTED:
                self.status = RunStatus.RUNNING

            case EventType.STAGE_STARTED if stage:
                stage.status = StageStatus.RUNNING
                stage.started_at = event.ts

            case EventType.STAGE_PROGRESS if stage:
                stage.progress = payload.get("message")
                stage.turn = payload.get("turn")
                stage.turn_of = payload.get("of")

            case EventType.AGENT_PROFILE if stage:
                kind = payload.get("kind", "dataset")
                text = payload.get("text")
                if text:
                    stage.profiles[kind] = text

            case EventType.AGENT_REASONING if stage:
                stage.reasoning.append(
                    ReasoningStepInfo(
                        index=payload.get("index", len(stage.reasoning)),
                        phase=payload.get("phase", ""),
                        observation=payload.get("observation", ""),
                        action=payload.get("action", ""),
                    )
                )

            case EventType.AGENT_TURN_COMPLETED if stage:
                turn = payload.get("turn")
                if turn:
                    stage.turns[turn] = payload.get("data")

            case EventType.AGENT_PLAN if stage:
                stage.plan_kind = payload.get("kind")
                stage.plan_items = payload.get("items", [])

            case EventType.AGENT_CODE if stage:
                stage.code = payload.get("code")

            case EventType.AGENT_RETRY if stage:
                stage.retries.append(
                    RetryInfo(
                        attempt=payload.get("attempt", payload.get("attempts", 0)),
                        max_attempts=payload.get("max_attempts", 0),
                        error=payload.get("error", ""),
                        exhausted=bool(payload.get("exhausted")),
                    )
                )

            case EventType.ARTIFACT_CREATED if stage:
                stage.artifacts.append(
                    ArtifactInfo(
                        kind=payload.get("kind", "chart"),
                        filename=payload.get("filename", ""),
                        url=payload.get("url", ""),
                        bytes=payload.get("bytes"),
                    )
                )

            case EventType.STAGE_COMPLETED if stage:
                stage.status = StageStatus.COMPLETED
                stage.completed_at = event.ts
                stage.duration_seconds = payload.get("duration_seconds")
                stage.progress = None
                if payload.get("summary"):
                    stage.summary = payload["summary"]

            case EventType.STAGE_FAILED if stage:
                stage.status = StageStatus.FAILED
                stage.completed_at = event.ts
                stage.duration_seconds = payload.get("duration_seconds")
                stage.error = payload.get("error")
                stage.progress = None

            case EventType.RUN_COMPLETED:
                self.status = RunStatus.COMPLETED
                self.completed_at = event.ts
                self.duration_seconds = payload.get("duration_seconds")
                self.report_url = payload.get("report_url")

            case EventType.RUN_FAILED:
                self.status = (
                    RunStatus.CANCELLED if payload.get("cancelled") else RunStatus.FAILED
                )
                self.completed_at = event.ts
                self.duration_seconds = payload.get("duration_seconds")
                self.error = payload.get("error")

            case _:
                pass

    # -- serialization ------------------------------------------------------ #

    def snapshot(self) -> RunSnapshot:
        return RunSnapshot(
            run_id=self.run_id,
            status=self.status,
            mode=self.mode,
            dataset_name=self.dataset_name,
            dataset_id=self.dataset_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            duration_seconds=self.duration_seconds,
            replay_of=self.replay_of,
            stage_order=list(STAGE_ORDER),
            stages=self.stages,
            report_url=self.report_url,
            error=self.error,
            last_seq=self.hub.last_seq,
            last_event_at=self.hub.last_event_at,
        )

    def summary(self) -> RunSummary:
        chart_count = sum(
            1
            for stage in self.stages.values()
            for artifact in stage.artifacts
            if artifact.kind == "chart"
        )
        return RunSummary(
            run_id=self.run_id,
            status=self.status,
            mode=self.mode,
            dataset_name=self.dataset_name,
            dataset_id=self.dataset_id,
            created_at=self.created_at,
            completed_at=self.completed_at,
            duration_seconds=self.duration_seconds,
            chart_count=chart_count,
            replay_of=self.replay_of,
        )

    def persist(self) -> None:
        """Mirror the snapshot to `run.json` so it survives a restart."""
        try:
            self.paths.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.paths.state_path.write_text(
                self.snapshot().model_dump_json(indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("run %s: could not persist run.json: %s", self.run_id, exc)


class RunManager:
    """Owns the run registry and the worker pool."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_runs,
            thread_name_prefix="eda-run",
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- lifecycle ---------------------------------------------------------- #

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the loop that worker threads will marshal events onto."""
        self._loop = loop

    def shutdown(self) -> None:
        # Do not wait: an in-flight stage can be minutes from finishing and a
        # blocking `responses.parse` is not interruptible either way.
        self._executor.shutdown(wait=False, cancel_futures=True)
        for run in self._runs.values():
            run.hub.close()

    @property
    def active_count(self) -> int:
        return sum(
            1
            for run in self._runs.values()
            if run.status in (RunStatus.PENDING, RunStatus.RUNNING)
        )

    # -- registry ----------------------------------------------------------- #

    def get(self, run_id: str) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            restored = self._restore_from_disk(run_id)
            if restored is None:
                raise RunNotFoundError(run_id)
            return restored
        return run

    def list_runs(self) -> list[RunSummary]:
        known = {run_id: run.summary() for run_id, run in self._runs.items()}

        # Surface completed runs from previous server processes too.
        if RUNS_DIR.is_dir():
            for directory in RUNS_DIR.iterdir():
                if directory.is_dir() and directory.name not in known:
                    restored = self._restore_from_disk(directory.name)
                    if restored is not None:
                        known[directory.name] = restored.summary()

        return sorted(known.values(), key=lambda item: item.created_at, reverse=True)

    def _restore_from_disk(self, run_id: str) -> Run | None:
        """Rebuild a run from its persisted event log.

        Used for runs created by an earlier server process. A run that was still
        in flight when the process died is reported as failed rather than left
        looking eternally "running".
        """
        paths = storage.run_paths(run_id)
        events = read_events_file(paths.events_path)
        if not events:
            return None

        started = events[0]
        dataset_name = started.payload.get("dataset_name", run_id)
        run = Run(
            run_id=run_id,
            dataset_name=dataset_name,
            dataset_id=started.payload.get("dataset_id"),
            paths=paths,
            mode=RunMode(started.payload.get("mode", RunMode.LIVE.value)),
            replay_of=started.payload.get("replay_of"),
        )
        run.created_at = started.ts

        for event in events:
            run.hub._seq = max(run.hub._seq, event.seq)  # keep seq monotonic
            run.hub._history.append(event)
            run.hub._last_event_at = event.ts
            run.apply(event)

        if run.status in (RunStatus.PENDING, RunStatus.RUNNING):
            run.status = RunStatus.FAILED
            run.error = "Server restarted while this run was in progress."
        run.hub.close()

        self._runs[run_id] = run
        return run

    # -- starting work ------------------------------------------------------ #

    def _emitter(self, run: Run):
        """Build the threadsafe `emit` handed to the orchestrator.

        Called from a worker thread; hops onto the event loop so all hub and
        snapshot mutation stays single-threaded.
        """
        loop = self._loop
        if loop is None:  # pragma: no cover - bind_loop runs at startup
            raise RuntimeError("RunManager has no event loop bound")

        def emit(
            event_type: EventType,
            payload: dict[str, Any],
            stage: StageId | None = None,
        ) -> None:
            def publish() -> None:
                event = run.hub.publish(event_type, payload, stage)
                run.apply(event)
                if event_type in (EventType.RUN_COMPLETED, EventType.RUN_FAILED):
                    run.persist()

            loop.call_soon_threadsafe(publish)

        return emit

    def create_live_run(self, dataset_id: str, dataset_path: Path) -> Run:
        """Register and launch a live run."""
        if self.active_count >= settings.max_concurrent_runs:
            raise RunCapacityError(
                f"{self.active_count} runs already in flight "
                f"(limit {settings.max_concurrent_runs})"
            )

        run_id = storage.new_id()
        paths = storage.create_run_paths(run_id)
        run = Run(
            run_id=run_id,
            dataset_name=dataset_path.stem,
            dataset_id=dataset_id,
            paths=paths,
            mode=RunMode.LIVE,
        )
        self._runs[run_id] = run
        run.persist()

        orchestrator = Orchestrator(
            run_id=run_id,
            dataset_path=dataset_path,
            paths=paths,
            emit=self._emitter(run),
            should_cancel=lambda: run.cancel_requested,
        )

        future = self._executor.submit(orchestrator.execute)
        future.add_done_callback(lambda fut: self._on_run_finished(run, fut))
        return run

    def _on_run_finished(self, run: Run, future) -> None:
        """Backstop for failures the orchestrator could not report itself."""
        exc = None
        try:
            exc = future.exception()
        except Exception:  # future was cancelled
            exc = None

        if exc is None or isinstance(exc, RunCancelled):
            return
        if run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            return

        # The orchestrator emits run.failed itself; reaching here means it could
        # not (e.g. an error inside emit). Close the stream so subscribers stop
        # waiting on a run that is no longer executing.
        logger.error("run %s ended without a terminal event: %s", run.run_id, exc)
        run.status = RunStatus.FAILED
        run.error = f"{type(exc).__name__}: {exc}"
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(run.hub.close)

    def create_replay_run(self, source_run_id: str) -> Run:
        """Re-stream a recorded run's events with no OpenAI calls.

        Artifact URLs keep pointing at the source run's files, so the replay
        renders real charts and a real report while costing nothing.
        """
        source_paths = storage.run_paths(source_run_id)
        events = read_events_file(source_paths.events_path)
        if not events:
            raise RunNotFoundError(source_run_id)

        run_id = storage.new_id()
        paths = storage.create_run_paths(run_id)
        source_name = events[0].payload.get("dataset_name", source_run_id)
        run = Run(
            run_id=run_id,
            dataset_name=source_name,
            dataset_id=events[0].payload.get("dataset_id"),
            paths=paths,
            mode=RunMode.REPLAY,
            replay_of=source_run_id,
        )
        self._runs[run_id] = run
        run.persist()

        loop = self._loop
        if loop is None:  # pragma: no cover
            raise RuntimeError("RunManager has no event loop bound")

        loop.create_task(replay_events(run, events))
        return run

    def request_cancel(self, run_id: str) -> Run:
        """Ask a run to stop.

        Cooperative only, and honestly so: a blocking `responses.parse` or
        `subprocess.run` cannot be interrupted, so the flag is checked between
        stages. The stage currently executing still runs to completion.
        """
        run = self.get(run_id)
        run.cancel_requested = True
        return run


#: Module-level singleton; wired to the event loop by `main.py`'s lifespan.
run_manager = RunManager()
