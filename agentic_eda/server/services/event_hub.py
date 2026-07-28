"""Per-run event fan-out with history, disk persistence and resumable replay.

The hub is the meeting point between a blocking worker thread (which runs the
agents) and any number of async SSE subscribers. Publishing is **async-loop
affine**: the worker never touches the hub directly, it calls a threadsafe
`emit` closure that hops onto the event loop via `call_soon_threadsafe`. That
keeps all mutation of `_history` and the subscriber queues single-threaded, so
no locking is needed.

Three properties matter:

* **A run outlives its subscribers.** The work happens in a thread pool, not in
  a request handler, so closing the browser does not cancel a run that costs
  real money and minutes.
* **History is replayable.** Every event carries a monotonic `seq`, so a
  reconnecting client sends `Last-Event-ID` and gets only what it missed.
* **History survives the process.** Events are appended to `events.jsonl` as
  they are published, which doubles as the source for replay mode and lets a
  completed run be inspected after a server restart.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from agentic_eda.server.models.events import (
    TERMINAL_EVENT_TYPES,
    EventEnvelope,
    EventType,
    StageId,
)
from agentic_eda.server.settings import settings

logger = logging.getLogger(__name__)


class EventHub:
    """Fan-out for one run's events."""

    def __init__(
        self,
        run_id: str,
        events_path: Path | None = None,
        max_buffered_events: int | None = None,
    ) -> None:
        self.run_id = run_id
        self._events_path = events_path
        self._max_buffered = max_buffered_events or settings.max_buffered_events

        self._history: list[EventEnvelope] = []
        self._subscribers: set[asyncio.Queue[EventEnvelope | None]] = set()
        self._seq = 0
        self._closed = False
        self._last_event_at: str | None = None

        if self._events_path is not None:
            self._events_path.parent.mkdir(parents=True, exist_ok=True)

    # -- state ------------------------------------------------------------- #

    @property
    def last_seq(self) -> int:
        return self._seq

    @property
    def last_event_at(self) -> str | None:
        return self._last_event_at

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # -- publishing (event loop thread only) -------------------------------- #

    def publish(
        self,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
        stage: StageId | None = None,
    ) -> EventEnvelope:
        """Assign the next `seq`, persist, and fan out to every subscriber."""
        self._seq += 1
        event = EventEnvelope(
            seq=self._seq,
            run_id=self.run_id,
            type=event_type,
            stage=stage,
            payload=payload or {},
        )
        self._last_event_at = event.ts

        self._append_to_disk(event)

        # Heartbeats are pure liveness signals; keeping them out of the history
        # stops a long quiet stage from evicting real events from the buffer.
        if event_type is not EventType.HEARTBEAT:
            self._history.append(event)
            if len(self._history) > self._max_buffered:
                del self._history[: len(self._history) - self._max_buffered]

        for queue in list(self._subscribers):
            self._offer(queue, event)

        if event_type in TERMINAL_EVENT_TYPES:
            self.close()

        return event

    def _offer(self, queue: "asyncio.Queue[EventEnvelope | None]", event: EventEnvelope) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # A subscriber that cannot keep up is dropped rather than allowed to
            # stall the run. Its EventSource will reconnect and replay from
            # Last-Event-ID, so nothing is permanently lost.
            logger.warning("run %s: dropping a subscriber that fell behind", self.run_id)
            self._subscribers.discard(queue)

    def close(self) -> None:
        """Signal end-of-stream to all current and future subscribers."""
        if self._closed:
            return
        self._closed = True
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)

    def _append_to_disk(self, event: EventEnvelope) -> None:
        if self._events_path is None or event.type is EventType.HEARTBEAT:
            return
        try:
            with self._events_path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        except OSError as exc:
            # Losing the durable log must not abort a paid-for run.
            logger.warning("run %s: could not append to events.jsonl: %s", self.run_id, exc)

    # -- subscribing ------------------------------------------------------- #

    def history_after(self, last_seq: int) -> list[EventEnvelope]:
        """Buffered events with `seq > last_seq`."""
        if last_seq <= 0:
            return list(self._history)
        return [event for event in self._history if event.seq > last_seq]

    def subscribe(self) -> "asyncio.Queue[EventEnvelope | None]":
        """Attach a new subscriber queue.

        Callers must pair this with `unsubscribe` in a `finally` block. If the
        hub is already closed the queue is pre-loaded with the sentinel so the
        subscriber terminates immediately after draining history.
        """
        queue: asyncio.Queue[EventEnvelope | None] = asyncio.Queue(
            maxsize=settings.subscriber_queue_size
        )
        self._subscribers.add(queue)
        if self._closed:
            queue.put_nowait(None)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[EventEnvelope | None]") -> None:
        self._subscribers.discard(queue)


def read_events_file(events_path: Path) -> list[EventEnvelope]:
    """Load a persisted event log, skipping any malformed trailing line.

    A run killed mid-write can leave a partial final line; that should degrade
    to "one missing event", not an unreadable log.
    """
    if not events_path.is_file():
        return []

    events: list[EventEnvelope] = []
    with events_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(EventEnvelope.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("%s:%d is not a valid event: %s", events_path, line_number, exc)
    return events


def iter_stage_events(events: Iterable[EventEnvelope]) -> Iterable[EventEnvelope]:
    """Filter out heartbeats — useful when rebuilding state from a log."""
    return (event for event in events if event.type is not EventType.HEARTBEAT)
