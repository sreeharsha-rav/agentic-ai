/**
 * The manual trigger.
 *
 * Starting a run is always an explicit click — never a side effect of uploading —
 * because a run takes 4-12 minutes and spends real OpenAI credit. The replay
 * picker sits alongside it so a previous run can be re-watched for free.
 */

import { memo } from 'react'

import type { DatasetInfo, RunSummaryInfo } from '../api/client'
import { formatDuration } from '../hooks/useElapsed'
import type { RunState } from '../state/runReducer'

interface Props {
  dataset: DatasetInfo | null
  state: RunState
  starting: boolean
  startError?: string
  runs: RunSummaryInfo[]
  keyConfigured: boolean
  onStart: () => void
  onReplay: (sourceRunId: string) => void
  onCancel: () => void
  onReset: () => void
}

function RunControlsImpl({
  dataset,
  state,
  starting,
  startError,
  runs,
  keyConfigured,
  onStart,
  onReplay,
  onCancel,
  onReset,
}: Props) {
  const active = state.status === 'pending' || state.status === 'running'
  const finished =
    state.status === 'completed' || state.status === 'failed' || state.status === 'cancelled'

  const replayable = runs.filter(
    (run) => run.status === 'completed' && run.mode === 'live',
  )

  const totalExpected = state.stageOrder.reduce(
    (sum, id) => sum + (state.stages[id]?.expectedSeconds ?? 0),
    0,
  )

  return (
    <section className="card" style={{ padding: '14px 16px', display: 'grid', gap: 12 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <button
          type="button"
          className="btn btn--primary"
          onClick={onStart}
          disabled={!dataset || active || starting}
        >
          {starting ? (
            <>
              <span className="spinner" aria-hidden="true" /> Starting…
            </>
          ) : (
            <>▶ Start EDA run</>
          )}
        </button>

        {active && (
          <button type="button" className="btn" onClick={onCancel}>
            Stop after current stage
          </button>
        )}

        {finished && (
          <button type="button" className="btn" onClick={onReset}>
            Clear and start over
          </button>
        )}

        {replayable.length > 0 && !active && (
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5 }}>
            <span className="muted">Replay a past run</span>
            <select
              className="btn btn--sm"
              defaultValue=""
              onChange={(event) => {
                if (event.target.value) {
                  onReplay(event.target.value)
                  event.target.value = ''
                }
              }}
            >
              <option value="">select…</option>
              {replayable.slice(0, 20).map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.dataset_name} · {run.chart_count} charts ·{' '}
                  {formatDuration(run.duration_seconds ?? undefined)}
                </option>
              ))}
            </select>
          </label>
        )}

        <span style={{ flex: 1 }} />

        {!dataset && <span className="faint">Upload a CSV first.</span>}
        {dataset && state.status === 'idle' && (
          <span className="faint">
            Typically ~{formatDuration(totalExpected)} across 4 agents.
          </span>
        )}
      </div>

      {!keyConfigured && (
        <div className="alert alert--warn">
          <span aria-hidden="true">!</span>
          <span>
            <strong>OPENAI_API_KEY is not configured.</strong> Uploads and replay work,
            but a live run will fail at the first agent. Add it to{' '}
            <code>agentic_eda/.env</code>.
          </span>
        </div>
      )}

      {startError && (
        <div className="alert" role="alert">
          <span aria-hidden="true">✕</span>
          <span>{startError}</span>
        </div>
      )}

      {state.mode === 'replay' && state.replayOf && (
        <div className="alert alert--warn" style={{ borderStyle: 'dashed' }}>
          <span aria-hidden="true">⟲</span>
          <span>
            Replaying recorded run <code>{state.replayOf}</code> — no OpenAI calls are
            being made. Timings are compressed.
          </span>
        </div>
      )}
    </section>
  )
}

export const RunControls = memo(RunControlsImpl)
