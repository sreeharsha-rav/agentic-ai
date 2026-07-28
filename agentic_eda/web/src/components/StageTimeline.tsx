/**
 * The sticky four-stage stepper — the primary spatial anchor for a run.
 *
 * Stays pinned while the page scrolls because "which agent is working and how
 * long has it been" is the question the user keeps re-asking across a 4-12
 * minute run, and it should never require scrolling back up to answer.
 */

import { memo } from 'react'

import { formatDuration, useElapsedSeconds } from '../hooks/useElapsed'
import type { RunState, StageState } from '../state/runReducer'
import type { StageId } from '../types/events'

interface Props {
  state: RunState
  selected: StageId | null
  onSelect: (stage: StageId) => void
}

const STATUS_GLYPH: Record<StageState['status'], string> = {
  pending: '○',
  running: '◐',
  completed: '●',
  failed: '✕',
  skipped: '–',
}

function TimelineStage({
  stage,
  index,
  selected,
  onSelect,
}: {
  stage: StageState
  index: number
  selected: boolean
  onSelect: (stage: StageId) => void
}) {
  const running = stage.status === 'running'
  const elapsed = useElapsedSeconds(stage.startedAt, running, stage.durationSeconds)
  const chartCount = stage.artifacts.filter((artifact) => artifact.kind === 'chart').length

  const dotClass =
    stage.status === 'running'
      ? 'dot dot--live'
      : stage.status === 'failed'
        ? 'dot dot--danger'
        : stage.status === 'completed'
          ? 'dot'
          : 'dot'

  return (
    <button
      type="button"
      className={`tlstage tlstage--${stage.status}${selected ? ' tlstage--selected' : ''}`}
      onClick={() => onSelect(stage.id)}
      aria-current={running ? 'step' : undefined}
    >
      <span className="tlstage__top">
        <span
          className={dotClass}
          style={{
            background:
              stage.status === 'completed'
                ? 'var(--success)'
                : stage.status === 'pending'
                  ? 'var(--text-faint)'
                  : undefined,
          }}
          aria-hidden="true"
        />
        <span className="tlstage__label">
          {index + 1}. {stage.label}
        </span>
      </span>
      <span className="tlstage__meta">
        <span aria-hidden="true">{STATUS_GLYPH[stage.status]}</span>
        {stage.status === 'pending' && <span>queued</span>}
        {running && (
          <span>
            {formatDuration(elapsed)} / ~{formatDuration(stage.expectedSeconds)}
          </span>
        )}
        {stage.status === 'completed' && (
          <span>
            {formatDuration(stage.durationSeconds)}
            {chartCount > 0 && ` · ${chartCount} charts`}
          </span>
        )}
        {stage.status === 'failed' && <span>failed</span>}
        {stage.retries.length > 0 && (
          <span className="badge badge--warn" style={{ padding: '0 5px' }}>
            ⟳ {stage.retries.length}
          </span>
        )}
      </span>
    </button>
  )
}

function StageTimelineImpl({ state, selected, onSelect }: Props) {
  return (
    <nav className="timeline" aria-label="Pipeline stages">
      {state.stageOrder.map((id, index) => {
        const stage = state.stages[id]
        if (!stage) return null
        return (
          <TimelineStage
            key={id}
            stage={stage}
            index={index}
            selected={selected === id}
            onSelect={onSelect}
          />
        )
      })}
    </nav>
  )
}

export const StageTimeline = memo(StageTimelineImpl)
