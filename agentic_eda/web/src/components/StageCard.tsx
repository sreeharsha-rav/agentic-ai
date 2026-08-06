/**
 * Per-stage detail: progress, reasoning, plan table, generated code, charts.
 *
 * Auto-expands while a stage is running and stays expanded once it has content,
 * so the card the user cares about is open without them managing disclosure state
 * during a live run.
 */

import { memo, useEffect, useState } from 'react'

import { formatDuration, useElapsedSeconds } from '../hooks/useElapsed'
import type { StageState } from '../state/runReducer'
import { STAGE_BLURBS } from '../types/events'
import { ChartGallery } from './ChartGallery'
import { CodeBlock } from './CodeBlock'
import { PlanTable } from './PlanTable'
import { ProgressTicker } from './ProgressTicker'
import { ReasoningStream } from './ReasoningStream'
import { RetryBanner } from './RetryBanner'

interface Props {
  stage: StageState
  index: number
}

const PROFILE_LABELS: Record<string, string> = {
  dataset: 'Dataset profile the agent was grounded on',
  correlation: 'Precomputed correlation report',
}

function StageCardImpl({ stage, index }: Props) {
  const running = stage.status === 'running'
  const hasContent =
    stage.reasoning.length > 0 ||
    stage.planItems.length > 0 ||
    stage.artifacts.length > 0 ||
    Boolean(stage.code) ||
    Boolean(stage.error)

  const [open, setOpen] = useState(running);

  // Follow the run: pop open when this stage starts working.
  useEffect(() => {
    if (running) setOpen(true)
  }, [running])

  const elapsed = useElapsedSeconds(stage.startedAt, running, stage.durationSeconds)
  const charts = stage.artifacts.filter((artifact) => artifact.kind === 'chart')
  const others = stage.artifacts.filter((artifact) => artifact.kind !== 'chart')

  const expectedCharts =
    stage.planItems.filter((item) => item.selected).length || undefined

  const statusBadge = (() => {
    switch (stage.status) {
      case 'running':
        return <span className="badge badge--accent">running · {formatDuration(elapsed)}</span>
      case 'completed':
        return (
          <span className="badge badge--success">
            completed · {formatDuration(stage.durationSeconds)}
          </span>
        )
      case 'failed':
        return <span className="badge badge--danger">failed</span>
      default:
        return <span className="badge">queued</span>
    }
  })()

  return (
    <section className={`card stagecard`}>
      <button
        type="button"
        className="stagecard__head"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="stagecard__chevron" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="stagecard__title">
          {index + 1}. {stage.label}
        </span>
        {stage.retries.length > 0 && (
          <span className="badge badge--warn">⟳ {stage.retries.length} self-correction</span>
        )}
        {charts.length > 0 && <span className="badge">{charts.length} charts</span>}
        {stage.reasoning.length > 0 && (
          <span className="badge">{stage.reasoning.length} steps</span>
        )}
        {statusBadge}
      </button>

      {open && (
        <div className="stagecard__body">
          {stage.status === 'pending' && (
            <p className="faint" style={{ margin: 0, fontSize: 12.5 }}>
              {STAGE_BLURBS[stage.id]}
            </p>
          )}

          <ProgressTicker stage={stage} />

          {stage.error && (
            <div className="alert" role="alert">
              <span aria-hidden="true">✕</span>
              <div style={{ minWidth: 0 }}>
                <strong>This stage failed.</strong>
                <pre className="pre" style={{ marginTop: 8, background: 'transparent', border: 'none', padding: 0 }}>
                  {stage.error}
                </pre>
              </div>
            </div>
          )}

          {stage.retries.length > 0 && <RetryBanner retries={stage.retries} />}

          {stage.summary && <p className="stagecard__summary">{stage.summary}</p>}

          {(stage.reasoning.length > 0 || running) && (
            <div>
              <div className="section__head" style={{ marginBottom: 8 }}>
                <h2>Reasoning</h2>
                <span className="faint" style={{ fontSize: 11.5 }}>
                  {stage.reasoning.length} step{stage.reasoning.length === 1 ? '' : 's'}
                </span>
              </div>
              <ReasoningStream steps={stage.reasoning} autoScroll={running} />
            </div>
          )}

          {stage.planKind && stage.planItems.length > 0 && (
            <PlanTable kind={stage.planKind} items={stage.planItems} />
          )}

          {stage.code && (
            <CodeBlock code={stage.code} language="python" revision={stage.codeRevision} />
          )}

          {Object.entries(stage.profiles).map(([kind, text]) => (
            <details className="disclosure" key={kind}>
              <summary>{PROFILE_LABELS[kind] ?? kind}</summary>
              <div className="disclosure__body">
                <pre className="pre">{text}</pre>
              </div>
            </details>
          ))}

          {(charts.length > 0 || (running && expectedCharts)) && (
            <div>
              <div className="section__head" style={{ marginBottom: 8 }}>
                <h2>Charts</h2>
                <span className="faint" style={{ fontSize: 11.5 }}>
                  {charts.length}
                  {expectedCharts ? ` of ~${expectedCharts}` : ''} rendered
                </span>
              </div>
              <ChartGallery charts={charts} expectedCount={running ? expectedCharts : undefined} />
            </div>
          )}

          {others.length > 0 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {others.map((artifact) => (
                <a
                  key={artifact.url}
                  className="btn btn--sm"
                  href={artifact.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  ↓ {artifact.filename}
                </a>
              ))}
            </div>
          )}

          {!hasContent && stage.status !== 'pending' && !running && (
            <p className="faint" style={{ margin: 0, fontSize: 12.5 }}>
              No output captured for this stage.
            </p>
          )}
        </div>
      )}
    </section>
  )
}

export const StageCard = memo(StageCardImpl)
