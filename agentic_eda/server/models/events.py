"""The streaming event protocol.

Every event the server emits is an `EventEnvelope` with a monotonic `seq`. The
sequence number is what makes the stream resumable: subscribers send
`Last-Event-ID` on reconnect and the server replays everything after it, while
the client ignores any `seq` it has already applied. That makes double delivery
harmless, which matters because a run lasts 4-12 minutes and will outlive at
least some client connections.

Agents emit short `(name, payload)` pairs through their `on_event` hook (see
`ProgressHook` in each agent module); the orchestrator maps those names onto the
`EventType` values below and stamps the stage.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class StageId(StrEnum):
    """The four pipeline stages, in execution order."""

    DATA_PREP = "data_prep"
    UNIVARIATE = "univariate"
    MULTIVARIATE = "multivariate"
    REPORT = "report"


STAGE_ORDER: tuple[StageId, ...] = (
    StageId.DATA_PREP,
    StageId.UNIVARIATE,
    StageId.MULTIVARIATE,
    StageId.REPORT,
)

STAGE_LABELS: dict[StageId, str] = {
    StageId.DATA_PREP: "Data Preparation",
    StageId.UNIVARIATE: "Univariate Analysis",
    StageId.MULTIVARIATE: "Multivariate Analysis",
    StageId.REPORT: "Report Synthesis",
}

# Observed wall-clock on the 186k-row sample dataset. Used purely to give the UI
# something honest to draw a progress bar against — a stage that overruns its
# estimate switches to an indeterminate indicator rather than claiming 100%.
STAGE_EXPECTED_SECONDS: dict[StageId, int] = {
    StageId.DATA_PREP: 50,
    StageId.UNIVARIATE: 105,
    StageId.MULTIVARIATE: 165,
    StageId.REPORT: 150,
}


class EventType(StrEnum):
    """Every event type a client may receive."""

    RUN_STARTED = "run.started"
    STAGE_STARTED = "stage.started"
    STAGE_PROGRESS = "stage.progress"
    AGENT_PROFILE = "agent.profile"
    AGENT_REASONING = "agent.reasoning"
    AGENT_TURN_COMPLETED = "agent.turn.completed"
    AGENT_PLAN = "agent.plan"
    AGENT_CODE = "agent.code"
    AGENT_RETRY = "agent.retry"
    ARTIFACT_CREATED = "artifact.created"
    STAGE_COMPLETED = "stage.completed"
    STAGE_FAILED = "stage.failed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    HEARTBEAT = "heartbeat"


#: Terminal event types — a client may close its EventSource once one arrives.
TERMINAL_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.RUN_COMPLETED, EventType.RUN_FAILED}
)


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunMode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"


ArtifactKind = Literal["chart", "cleaned_csv", "report"]


def utc_now_iso() -> str:
    """Timestamp used on every envelope."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EventEnvelope(BaseModel):
    """One event on the wire.

    Serialized into an SSE frame as::

        id: {seq}
        event: {type}
        data: {json}
    """

    seq: int = Field(description="Monotonic per-run sequence number; the SSE event id.")
    ts: str = Field(default_factory=utc_now_iso, description="ISO-8601 UTC timestamp.")
    run_id: str
    type: EventType
    stage: StageId | None = Field(
        default=None,
        description="Owning stage, or None for run-level and heartbeat events.",
    )
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Render as a single SSE frame (including the trailing blank line)."""
        data = self.model_dump_json()
        return f"id: {self.seq}\nevent: {self.type.value}\ndata: {data}\n\n"


#: Maps the short names agents pass to `on_event` onto wire event types. The
#: agents deliberately know nothing about the envelope; this is the only place
#: the two vocabularies meet.
AGENT_EVENT_TYPES: dict[str, EventType] = {
    "progress": EventType.STAGE_PROGRESS,
    "profile": EventType.AGENT_PROFILE,
    "reasoning": EventType.AGENT_REASONING,
    "turn_completed": EventType.AGENT_TURN_COMPLETED,
    "plan": EventType.AGENT_PLAN,
    "code": EventType.AGENT_CODE,
    "retry": EventType.AGENT_RETRY,
    "retry_exhausted": EventType.AGENT_RETRY,
    "artifact": EventType.ARTIFACT_CREATED,
}
