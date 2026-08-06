/**
 * EventSource wrapper for a run's SSE stream.
 *
 * `EventSource` is used rather than `fetch` + `ReadableStream` for two reasons
 * that matter over a 4-12 minute run: the browser reconnects automatically on a
 * dropped connection, and it resends `Last-Event-ID` so the server can replay
 * only what was missed. Both come for free and would otherwise be hand-rolled.
 *
 * Note the server sets every frame's `id:` to the event `seq`, so the browser's
 * `Last-Event-ID` and the reducer's dedup cursor are the same number.
 */

import type { EdaEvent, EdaEventType } from '../types/events'
import { isTerminal } from '../types/events'

/** Every event type the server can send; each needs an explicit listener. */
const EVENT_TYPES: EdaEventType[] = [
  'run.started',
  'stage.started',
  'stage.progress',
  'agent.profile',
  'agent.reasoning',
  'agent.turn.completed',
  'agent.plan',
  'agent.code',
  'agent.retry',
  'artifact.created',
  'stage.completed',
  'stage.failed',
  'run.completed',
  'run.failed',
  'heartbeat',
]

export interface EventStreamHandlers {
  onEvent: (event: EdaEvent) => void
  onOpen?: () => void
  onReconnecting?: () => void
  onClose?: () => void
  onError?: (message: string) => void
}

export interface EventStreamHandle {
  close: () => void
}

/**
 * Subscribe to `runId`'s events.
 *
 * Returns a handle whose `close()` is safe to call repeatedly. Closing only ends
 * this subscription — the run itself keeps executing server-side, which is
 * deliberate given what a run costs.
 */
export function subscribeToRun(
  runId: string,
  handlers: EventStreamHandlers,
): EventStreamHandle {
  const source = new EventSource(`/api/runs/${runId}/events`)
  let closed = false

  const close = () => {
    if (closed) return
    closed = true
    source.close()
    handlers.onClose?.()
  }

  source.onopen = () => {
    if (!closed) handlers.onOpen?.()
  }

  source.onerror = () => {
    if (closed) return
    // EventSource reports both a transient drop and a hard failure here. CLOSED
    // means it has given up; anything else means it is retrying on its own.
    if (source.readyState === EventSource.CLOSED) {
      handlers.onError?.('Event stream closed unexpectedly.')
      close()
    } else {
      handlers.onReconnecting?.()
    }
  }

  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (message) => {
      if (closed) return

      let parsed: EdaEvent
      try {
        parsed = JSON.parse((message as MessageEvent).data) as EdaEvent
      } catch {
        handlers.onError?.(`Received a malformed ${type} event.`)
        return
      }

      handlers.onEvent(parsed)

      // Close on a terminal event so the browser does not immediately reconnect
      // to a finished run and replay its whole history.
      if (isTerminal(parsed.type)) {
        close()
      }
    })
  }

  return { close }
}
