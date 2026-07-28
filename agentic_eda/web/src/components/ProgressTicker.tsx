/**
 * What the user looks at during the long silences.
 *
 * A single LLM call in the multivariate stage can run for four minutes with no
 * events at all. Three things make that read as "working" rather than "hung":
 *
 * 1. The elapsed timer ticks locally, so something is always moving.
 * 2. The latest sub-step is named ("Turn 2/2: generating matplotlib code"), so
 *    the wait is attributable.
 * 3. Progress is measured against an observed expected duration, and switches to
 *    an indeterminate bar once it overruns rather than claiming 99% forever.
 */

import { memo } from 'react'

import { formatDuration, useElapsedSeconds } from '../hooks/useElapsed'
import type { StageState } from '../state/runReducer'

interface Props {
  stage: StageState
}

function ProgressTickerImpl({ stage }: Props) {
  const running = stage.status === 'running'
  const elapsed = useElapsedSeconds(stage.startedAt, running, stage.durationSeconds)

  if (!running) return null

  const fraction = stage.expectedSeconds > 0 ? elapsed / stage.expectedSeconds : 0
  // Cap the determinate bar well short of full: finishing the bar before the
  // stage finishes is exactly the lie that makes progress bars untrustworthy.
  const overrunning = fraction >= 0.9
  const width = Math.min(90, Math.round(fraction * 100))

  const turnLabel =
    stage.turn && stage.turnOf ? `Turn ${stage.turn}/${stage.turnOf}` : undefined

  return (
    <div className="ticker">
      <div className="ticker__row">
        <span className="spinner" aria-hidden="true" />
        <span className="ticker__msg" aria-live="polite">
          {turnLabel && <strong>{turnLabel}: </strong>}
          {stage.progress ?? 'working…'}
        </span>
        <span className="ticker__time">
          {formatDuration(elapsed)}
          <span className="faint"> / ~{formatDuration(stage.expectedSeconds)}</span>
        </span>
      </div>
      <div
        className="progressbar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={overrunning ? undefined : width}
        aria-label={`${stage.label} progress`}
      >
        <div
          className={`progressbar__fill${overrunning ? ' progressbar__fill--indeterminate' : ''}`}
          style={{ width: `${overrunning ? 35 : width}%` }}
        />
      </div>
      {overrunning && (
        <span className="faint" style={{ fontSize: 11.5 }}>
          Running longer than the typical {formatDuration(stage.expectedSeconds)} — still
          streaming, no action needed.
        </span>
      )}
    </div>
  )
}

export const ProgressTicker = memo(ProgressTickerImpl)
