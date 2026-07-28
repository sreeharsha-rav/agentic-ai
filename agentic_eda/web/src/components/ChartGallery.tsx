/**
 * Chart tiles that append as `artifact.created` events arrive.
 *
 * During a run this is the most concrete evidence of progress available — a
 * chart appearing is unambiguous. Placeholder skeletons are drawn for charts the
 * agent said it planned but has not written yet, so the grid shows the shape of
 * what is coming rather than reflowing on every arrival.
 */

import { memo, useCallback, useEffect, useState } from 'react'

import { formatBytes } from '../hooks/useElapsed'
import type { Artifact } from '../types/events'

interface Props {
  charts: Artifact[]
  /** Count the agent expects, used to render pending placeholders. */
  expectedCount?: number
}

function ChartTile({
  chart,
  onOpen,
}: {
  chart: Artifact
  onOpen: (chart: Artifact) => void
}) {
  const [broken, setBroken] = useState(false)

  return (
    <button type="button" className="chart" onClick={() => onOpen(chart)}>
      {broken ? (
        <div className="chart__missing">Chart image unavailable</div>
      ) : (
        <img
          src={chart.url}
          alt={`Generated chart: ${chart.filename}`}
          loading="lazy"
          onError={() => setBroken(true)}
        />
      )}
      <span className="chart__caption" title={`${chart.filename} · ${formatBytes(chart.bytes)}`}>
        {chart.filename}
      </span>
    </button>
  )
}

function Lightbox({
  charts,
  index,
  onClose,
  onNavigate,
}: {
  charts: Artifact[]
  index: number
  onClose: () => void
  onNavigate: (next: number) => void
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowRight') onNavigate((index + 1) % charts.length)
      if (event.key === 'ArrowLeft') onNavigate((index - 1 + charts.length) % charts.length)
    }
    window.addEventListener('keydown', onKey)
    // Stop the page behind the overlay from scrolling.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [index, charts.length, onClose, onNavigate])

  const chart = charts[index]
  if (!chart) return null

  return (
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={`Chart ${index + 1} of ${charts.length}: ${chart.filename}`}
      onClick={onClose}
    >
      <img src={chart.url} alt={chart.filename} onClick={(event) => event.stopPropagation()} />
      <div className="lightbox__bar" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="btn btn--sm"
          onClick={() => onNavigate((index - 1 + charts.length) % charts.length)}
          aria-label="Previous chart"
        >
          ‹ Prev
        </button>
        <span>
          {chart.filename} · {index + 1}/{charts.length}
        </span>
        <button
          type="button"
          className="btn btn--sm"
          onClick={() => onNavigate((index + 1) % charts.length)}
          aria-label="Next chart"
        >
          Next ›
        </button>
        <a className="btn btn--sm" href={chart.url} target="_blank" rel="noreferrer">
          Open original
        </a>
        <button type="button" className="btn btn--sm" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}

function ChartGalleryImpl({ charts, expectedCount }: Props) {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  const open = useCallback((chart: Artifact) => {
    setOpenIndex(charts.findIndex((candidate) => candidate.url === chart.url))
  }, [charts])

  const pending = Math.max(0, (expectedCount ?? 0) - charts.length)

  if (charts.length === 0 && pending === 0) return null

  return (
    <>
      <div className="gallery">
        {charts.map((chart) => (
          <ChartTile key={chart.url} chart={chart} onOpen={open} />
        ))}
        {Array.from({ length: pending }, (_, index) => (
          <div className="chartskeleton" key={`pending-${index}`} aria-hidden="true" />
        ))}
      </div>
      {openIndex !== null && openIndex >= 0 && (
        <Lightbox
          charts={charts}
          index={openIndex}
          onClose={() => setOpenIndex(null)}
          onNavigate={setOpenIndex}
        />
      )}
    </>
  )
}

export const ChartGallery = memo(ChartGalleryImpl)
