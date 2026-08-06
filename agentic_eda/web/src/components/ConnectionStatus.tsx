/**
 * Stream health, top-right.
 *
 * "Last event 34s ago" is doing real work here: during a four-minute LLM call the
 * absence of events is normal, and the user needs to be able to distinguish
 * healthy silence from a dead connection. The server's 10s heartbeat keeps this
 * number small whenever the stream is genuinely alive, so a large number is a
 * meaningful signal rather than noise.
 */

import { memo } from 'react'

import { useTicker } from '../hooks/useElapsed'
import type { RunState } from '../state/runReducer'

interface Props {
  state: RunState
}

function ConnectionStatusImpl({ state }: Props) {
  const active = state.status === 'pending' || state.status === 'running'
  useTicker(active, 1000)

  if (state.status === 'idle') {
    return <span className="badge">idle</span>
  }

  const secondsSinceEvent =
    state.lastEventAt !== undefined ? (Date.now() - state.lastEventAt) / 1000 : undefined

  // Heartbeats land every ~10s, so silence past ~30s is worth flagging.
  const stale = secondsSinceEvent !== undefined && secondsSinceEvent > 30

  const runBadge = (() => {
    switch (state.status) {
      case 'running':
        return (
          <span className="badge badge--accent">
            <span className="dot dot--live" aria-hidden="true" />
            {state.mode === 'replay' ? 'replaying' : 'live'}
          </span>
        )
      case 'pending':
        return <span className="badge badge--accent">starting…</span>
      case 'completed':
        return <span className="badge badge--success">completed</span>
      case 'failed':
        return <span className="badge badge--danger">failed</span>
      case 'cancelled':
        return <span className="badge badge--warn">cancelled</span>
      default:
        return null
    }
  })()

  return (
    <>
      {runBadge}

      {state.connection === 'reconnecting' && (
        <span className="badge badge--warn">
          <span className="dot dot--warn" aria-hidden="true" /> reconnecting
        </span>
      )}

      {active && secondsSinceEvent !== undefined && (
        <span
          className={`badge${stale ? ' badge--warn' : ''}`}
          title="Time since the last event or heartbeat. The server heartbeats every 10s."
          aria-live="off"
        >
          last event {Math.round(secondsSinceEvent)}s ago
        </span>
      )}

      {state.chartCount > 0 && <span className="badge">{state.chartCount} charts</span>}

      {state.runId && (
        <span className="badge badge--mono" title="Run id">
          {state.runId}
        </span>
      )}
    </>
  )
}

export const ConnectionStatus = memo(ConnectionStatusImpl)
