/**
 * Renders the final markdown report.
 *
 * The one subtlety is image resolution. `report/agent.py::_md_image_link` writes
 * links relative to the report's own directory (`../charts/univariate/sales.png`)
 * so the `.md` stays correct for anyone opening it on disk. Inside this SPA the
 * document base is the app, not the report, so those links would 404. Rather than
 * rewriting the markdown server-side, the server returns a `base_url` and every
 * relative src is resolved against it here.
 */

import { memo, useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { getReport, type ReportPayload } from '../api/client'

interface Props {
  runId: string
  /** Bump to refetch, e.g. once run.completed arrives. */
  ready: boolean
}

function ReportViewerImpl({ runId, ready }: Props) {
  const [report, setReport] = useState<ReportPayload | null>(null)
  const [error, setError] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!ready || !runId) return

    let cancelled = false
    setLoading(true)
    setError(undefined)

    getReport(runId)
      .then((payload) => {
        if (!cancelled) setReport(payload)
      })
      .catch((fetchError: unknown) => {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError.message : 'Could not load the report.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [runId, ready])

  if (!ready) return null

  if (loading) {
    return (
      <div className="card empty">
        <span className="spinner" aria-hidden="true" /> Loading the report…
      </div>
    )
  }

  if (error) {
    return (
      <div className="alert" role="alert">
        <span aria-hidden="true">✕</span>
        <span>{error}</span>
      </div>
    )
  }

  if (!report) return null

  return (
    <article className="card report">
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => {
          // Leave absolute and data URLs alone; resolve the report's own relative
          // links against the artifact directory the server pointed us at.
          if (/^[a-z][a-z0-9+.-]*:/i.test(url) || url.startsWith('/')) {
            return url
          }
          try {
            return new URL(url, new URL(report.base_url, window.location.origin)).toString()
          } catch {
            return url
          }
        }}
      >
        {report.markdown}
      </Markdown>

      <div style={{ marginTop: 20, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <a className="btn btn--sm" href={report.url} target="_blank" rel="noreferrer">
          ↓ Download markdown
        </a>
      </div>
    </article>
  )
}

export const ReportViewer = memo(ReportViewerImpl)
