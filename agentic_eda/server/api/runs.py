"""Run control and the SSE event stream.

Creation and subscription are split on purpose:

* `POST /api/runs` triggers the work and returns 202 immediately.
* `GET /api/runs/{id}/events` is a separate GET, so the browser's native
  `EventSource` can be used — which brings automatic reconnection and
  `Last-Event-ID` resume for free. Both matter when a run lasts 4-12 minutes.

Because the run executes in a thread pool rather than in this request's task,
closing the stream never cancels the run.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Header, Request, Response, status
from fastapi.responses import StreamingResponse

from agentic_eda.server.models.events import (
    EventEnvelope,
    EventType,
    RunMode,
    RunStatus,
)
from agentic_eda.server.models.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    ReportResponse,
    RunSnapshot,
    RunSummary,
)
from agentic_eda.server.services import storage
from agentic_eda.server.services.run_manager import (
    Run,
    RunCapacityError,
    RunNotFoundError,
    run_manager,
)
from agentic_eda.server.services.storage import ARTIFACTS_URL_PREFIX
from agentic_eda.server.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _events_url(run_id: str) -> str:
    return f"/api/runs/{run_id}/events"


def _get_run_or_404(run_id: str) -> Run:
    try:
        return run_manager.get(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No run with id '{run_id}'.",
        ) from exc


@router.post("", response_model=CreateRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_run(body: CreateRunRequest, response: Response) -> CreateRunResponse:
    """Trigger a live run, or replay a recorded one.

    Returns as soon as the work is queued; all progress arrives over the event
    stream.
    """
    if body.mode is RunMode.REPLAY:
        if not body.source_run_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mode=replay requires 'source_run_id'.",
            )
        try:
            run = run_manager.create_replay_run(body.source_run_id)
        except RunNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No recorded events for run '{body.source_run_id}'. "
                    "Only completed runs can be replayed."
                ),
            ) from exc
    else:
        if not body.dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A 'dataset_id' is required to start a run.",
            )

        dataset_path = storage.dataset_path(body.dataset_id)
        if dataset_path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No dataset with id '{body.dataset_id}'. Upload a CSV first.",
            )

        try:
            run = run_manager.create_live_run(body.dataset_id, dataset_path)
        except RunCapacityError as exc:
            # 429 rather than 503: the request is valid, the client just needs to
            # wait for a slot. Each run is minutes of paid compute.
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc

    response.headers["Location"] = _events_url(run.run_id)
    return CreateRunResponse(
        run_id=run.run_id,
        status=run.status,
        mode=run.mode,
        events_url=_events_url(run.run_id),
    )


@router.get("", response_model=list[RunSummary])
async def list_runs() -> list[RunSummary]:
    """All known runs, newest first (including ones from earlier processes)."""
    return run_manager.list_runs()


@router.get("/{run_id}", response_model=RunSnapshot)
async def get_run(run_id: str) -> RunSnapshot:
    """Full run state — lets a reloaded page rehydrate in one request."""
    return _get_run_or_404(run_id).snapshot()


@router.post("/{run_id}/cancel", response_model=RunSnapshot)
async def cancel_run(run_id: str) -> RunSnapshot:
    """Request cancellation.

    Cooperative only: the flag is checked between stages, so whichever stage is
    executing runs to completion. A blocking OpenAI call cannot be interrupted.
    """
    _get_run_or_404(run_id)
    return run_manager.request_cancel(run_id).snapshot()


@router.get("/{run_id}/report", response_model=ReportResponse)
async def get_run_report(run_id: str) -> ReportResponse:
    """The markdown report plus the base URL its relative image links resolve against."""
    run = _get_run_or_404(run_id)

    # A replay's artifacts live under the source run's directory.
    artifact_run_id = run.replay_of or run.run_id
    paths = storage.run_paths(artifact_run_id)
    candidates = sorted(paths.reports_dir.glob("*.md"))
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' has not produced a report yet.",
        )

    report_path = candidates[0]
    return ReportResponse(
        run_id=run_id,
        markdown=report_path.read_text(encoding="utf-8"),
        base_url=f"{ARTIFACTS_URL_PREFIX}/{artifact_run_id}/reports/",
        url=f"{ARTIFACTS_URL_PREFIX}/{artifact_run_id}/reports/{report_path.name}",
    )


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Subscribe to a run's events as Server-Sent Events.

    Replays any buffered events after `Last-Event-ID`, then streams live. Emits a
    heartbeat during quiet periods so intermediaries do not drop the connection
    and the client can show a "last event N seconds ago" freshness indicator —
    a stage can legitimately be silent for minutes.
    """
    run = _get_run_or_404(run_id)

    try:
        resume_from = int(last_event_id) if last_event_id else 0
    except ValueError:
        resume_from = 0

    async def event_stream():
        # Subscribe before replaying history so nothing published in between is
        # lost; the seq-based dedup on the client makes any overlap harmless.
        queue = run.hub.subscribe()
        started = time.monotonic()

        try:
            # Advise the browser's automatic reconnect interval.
            yield "retry: 3000\n\n"

            for event in run.hub.history_after(resume_from):
                yield event.to_sse()

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=settings.heartbeat_seconds
                    )
                except asyncio.TimeoutError:
                    active = next(
                        (
                            stage.id.value
                            for stage in run.stages.values()
                            if stage.status == "running"
                        ),
                        None,
                    )
                    heartbeat = EventEnvelope(
                        seq=run.hub.last_seq,
                        run_id=run.run_id,
                        type=EventType.HEARTBEAT,
                        payload={
                            "elapsed_seconds": round(time.monotonic() - started, 1),
                            "active_stage": active,
                            "run_status": run.status.value,
                        },
                    )
                    # Heartbeats reuse the last real seq so they never advance the
                    # client's dedup cursor or its Last-Event-ID.
                    yield heartbeat.to_sse()
                    continue

                if event is None:  # end-of-stream sentinel
                    break

                yield event.to_sse()

            # A run that finished before this subscriber attached still needs a
            # terminal frame, otherwise the client waits forever.
            if run.status in (
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            ):
                yield ": stream closed\n\n"

        except asyncio.CancelledError:
            # Client went away. The run itself continues in the worker pool.
            logger.debug("run %s: subscriber disconnected", run_id)
            raise
        finally:
            run.hub.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Stops nginx and friends from buffering the stream into uselessness.
            "X-Accel-Buffering": "no",
        },
    )
