/**
 * Live-appending chain of thought.
 *
 * Wrapped in an `aria-live` region because these arrive over minutes: a screen
 * reader user should hear that the agent is producing findings, not sit in
 * silence while the DOM quietly grows.
 */

import { memo, useEffect, useRef } from 'react'

import type { ReasoningStep } from '../types/events'

interface Props {
  steps: ReasoningStep[]
  /** Keep the newest step in view only while the stage is actively producing them. */
  autoScroll?: boolean
}

function ReasoningStreamImpl({ steps, autoScroll = false }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!autoScroll || steps.length === 0) return
    endRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [steps.length, autoScroll])

  if (steps.length === 0) {
    return <p className="faint" style={{ margin: 0, fontSize: 12.5 }}>No reasoning steps yet.</p>
  }

  return (
    <div className="reasoning" aria-live="polite" aria-relevant="additions">
      {steps.map((step, index) => (
        <div className="rstep" key={`${step.phase}-${step.index}-${index}`}>
          <span className="rstep__phase">{step.phase || 'step'}</span>
          <div className="rstep__text">
            <span className="rstep__obs">{step.observation}</span>
            <span className="rstep__act">{step.action}</span>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}

export const ReasoningStream = memo(ReasoningStreamImpl)
