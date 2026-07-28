"""Replay a recorded run's event log without touching OpenAI.

A live run costs 4-12 minutes and real API spend, which makes it a poor
development and demo loop. Replay re-publishes a completed run's `events.jsonl`
through the normal hub, so the client code path is identical — but the original
inter-event gaps are compressed, turning a twelve-minute run into a few seconds.

Artifact URLs are rewritten to point at the *source* run's files, so a replay
renders the real charts and the real report.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Sequence

from agentic_eda.server.models.events import EventEnvelope, EventType, RunMode
from agentic_eda.server.services.storage import ARTIFACTS_URL_PREFIX
from agentic_eda.server.settings import settings

if TYPE_CHECKING:
    from agentic_eda.server.services.run_manager import Run

logger = logging.getLogger(__name__)


def _parse_ts(value: str) -> float | None:
    from datetime import datetime

    try:
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, TypeError):
        return None


def _gap_seconds(previous: EventEnvelope, current: EventEnvelope) -> float:
    """Real gap between two events, compressed and clamped for replay."""
    start, end = _parse_ts(previous.ts), _parse_ts(current.ts)
    if start is None or end is None:
        return 0.05

    real_gap = max(0.0, end - start)
    scaled = real_gap / max(settings.replay_speed, 1e-6)
    return min(scaled, settings.replay_max_gap_seconds)


def _rewrite_payload(
    event: EventEnvelope,
    run: "Run",
    source_run_id: str,
) -> dict:
    """Re-point a recorded payload at the replay run, keeping source artifacts."""
    payload = dict(event.payload)

    if event.type is EventType.RUN_STARTED:
        payload["run_id"] = run.run_id
        payload["mode"] = RunMode.REPLAY.value
        payload["replay_of"] = source_run_id
        return payload

    # Artifacts still live under the source run's directory.
    for key in ("url", "report_url"):
        url = payload.get(key)
        if isinstance(url, str) and url.startswith(f"{ARTIFACTS_URL_PREFIX}/{run.run_id}/"):
            payload[key] = url.replace(
                f"{ARTIFACTS_URL_PREFIX}/{run.run_id}/",
                f"{ARTIFACTS_URL_PREFIX}/{source_run_id}/",
                1,
            )

    return payload


async def replay_events(run: "Run", events: Sequence[EventEnvelope]) -> None:
    """Publish `events` onto `run`'s hub with compressed pacing."""
    source_run_id = run.replay_of or ""
    logger.info(
        "run %s: replaying %d events from %s", run.run_id, len(events), source_run_id
    )

    previous: EventEnvelope | None = None
    try:
        for event in events:
            if event.type is EventType.HEARTBEAT:
                continue
            if run.cancel_requested:
                logger.info("run %s: replay cancelled", run.run_id)
                break

            if previous is not None:
                delay = _gap_seconds(previous, event)
                if delay > 0:
                    await asyncio.sleep(delay)
            previous = event

            published = run.hub.publish(
                event.type,
                _rewrite_payload(event, run, source_run_id),
                event.stage,
            )
            run.apply(published)

        run.persist()
    except asyncio.CancelledError:
        logger.info("run %s: replay task cancelled", run.run_id)
        raise
    except Exception:
        logger.exception("run %s: replay failed", run.run_id)
        raise
    finally:
        run.hub.close()
