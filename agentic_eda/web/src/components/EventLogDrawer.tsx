/**
 * Raw envelope log.
 *
 * The projected stage cards are the product; this is the receipt. When a card
 * looks wrong, being able to read the actual events — with their seq numbers — is
 * the fastest way to tell a server bug from a reducer bug.
 */

import { memo, useState } from 'react'

import type { LogEntry } from '../state/runReducer'

interface Props {
  entries: LogEntry[]
  lastSeq: number
}

function EventLogDrawerImpl({ entries, lastSeq }: Props) {
  const [open, setOpen] = useState(false)

  if (!open) {
    return (
      <button
        type="button"
        className="btn btn--sm logtoggle"
        onClick={() => setOpen(true)}
        aria-label="Open the raw event log"
      >
        ⌗ Event log {entries.length > 0 && <span className="badge">{entries.length}</span>}
      </button>
    )
  }

  return (
    <aside className="drawer" role="dialog" aria-label="Raw event log">
      <div className="drawer__head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 13 }}>Raw event log</strong>
          <span className="badge badge--mono">{entries.length} buffered</span>
          <span className="badge badge--mono">last seq {lastSeq}</span>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      <div className="drawer__body">
        {entries.length === 0 ? (
          <p className="faint" style={{ fontSize: 12.5 }}>
            No events yet. Start a run to see the stream.
          </p>
        ) : (
          entries.map((entry) => (
            <div className="logrow" key={entry.seq}>
              <span className="logrow__seq">{entry.seq}</span>
              <div style={{ minWidth: 0 }}>
                <div>
                  <span className="logrow__type">{entry.type}</span>
                  {entry.stage && <span className="faint"> · {entry.stage}</span>}
                </div>
                <div className="logrow__payload">
                  {JSON.stringify(entry.payload, null, 1).slice(0, 600)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

export const EventLogDrawer = memo(EventLogDrawerImpl)
