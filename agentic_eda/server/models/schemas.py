"""REST request/response bodies.

These describe the non-streaming surface: dataset upload, run creation, and the
snapshot endpoints a client uses to rehydrate after a page reload instead of
replaying the whole event history.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from .events import ArtifactKind, RunMode, RunStatus, StageId, StageStatus


class DatasetInfo(BaseModel):
    """An uploaded CSV, plus the profile the agents will be grounded on."""

    dataset_id: str
    filename: str
    bytes: int
    uploaded_at: str
    profile: str = Field(
        description="Plain-text profile from utils.profile_dataset: shape, dtypes, "
        "null counts, distinct counts and a head preview."
    )
    rows: int | None = Field(default=None, description="Parsed out of the profile when available.")
    columns: int | None = Field(default=None)


class DatasetSummary(BaseModel):
    """Listing entry — omits the (large) profile text."""

    dataset_id: str
    filename: str
    bytes: int
    uploaded_at: str


class CreateRunRequest(BaseModel):
    """Trigger a live run, or replay a recorded one.

    Exactly one of `dataset_id` (live) or `source_run_id` (replay) is required.
    """

    dataset_id: str | None = None
    mode: RunMode = RunMode.LIVE
    source_run_id: str | None = Field(
        default=None,
        description="For mode=replay: the completed run whose events.jsonl to re-stream.",
    )


class CreateRunResponse(BaseModel):
    run_id: str
    status: RunStatus
    mode: RunMode
    events_url: str


class ArtifactInfo(BaseModel):
    kind: ArtifactKind
    filename: str
    url: str
    bytes: int | None = None


class RetryInfo(BaseModel):
    attempt: int
    max_attempts: int
    error: str
    exhausted: bool = False


class ReasoningStepInfo(BaseModel):
    """Mirrors the agents' phase/observation/action convention."""

    index: int
    phase: str
    observation: str
    action: str


class StageSnapshot(BaseModel):
    """Everything known about one stage — the shape the UI renders per card."""

    id: StageId
    label: str
    status: StageStatus
    expected_seconds: int
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    progress: str | None = Field(default=None, description="Latest human-readable sub-step.")
    turn: int | None = None
    turn_of: int | None = None
    reasoning: list[ReasoningStepInfo] = Field(default_factory=list)
    plan_kind: Literal["variable", "relationship"] | None = None
    plan_items: list[dict[str, Any]] = Field(default_factory=list)
    code: str | None = None
    profiles: dict[str, str] = Field(
        default_factory=dict,
        description="Grounding text the agent saw, keyed by kind ('dataset', 'correlation').",
    )
    turns: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured per-turn agent output, keyed by turn name.",
    )
    retries: list[RetryInfo] = Field(default_factory=list)
    artifacts: list[ArtifactInfo] = Field(default_factory=list)
    summary: str | None = None
    error: str | None = None


class RunSummary(BaseModel):
    """Listing entry for the run index."""

    run_id: str
    status: RunStatus
    mode: RunMode
    dataset_name: str
    dataset_id: str | None = None
    created_at: str
    completed_at: str | None = None
    duration_seconds: float | None = None
    chart_count: int = 0
    replay_of: str | None = None


class RunSnapshot(BaseModel):
    """Full run state, used to rehydrate a client without replaying events."""

    run_id: str
    status: RunStatus
    mode: RunMode
    dataset_name: str
    dataset_id: str | None = None
    created_at: str
    completed_at: str | None = None
    duration_seconds: float | None = None
    replay_of: str | None = None
    stage_order: list[StageId]
    stages: dict[StageId, StageSnapshot]
    report_url: str | None = None
    error: str | None = None
    last_seq: int = 0
    last_event_at: str | None = None


class ReportResponse(BaseModel):
    """The markdown report plus the base URL its relative image links resolve against.

    `report.agent._md_image_link` writes links like `../charts/univariate/sales.png`,
    relative to the report's own directory. Rather than rewriting the markdown
    (which would break the file for anyone opening it directly), the client
    resolves each `src` against `base_url`.
    """

    run_id: str
    markdown: str
    base_url: str
    url: str
