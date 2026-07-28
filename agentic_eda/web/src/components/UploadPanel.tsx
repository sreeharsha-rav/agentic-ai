/**
 * Step 1: get a CSV onto the server and show what the agents will actually see.
 *
 * The profile preview matters more than it looks: it is the exact text the data
 * prep agent is grounded on, so showing it lets the user sanity-check the data
 * before committing to a run that costs several minutes and real API spend.
 */

import { memo, useCallback, useRef, useState } from 'react'

import { ApiError, uploadDataset, type DatasetInfo } from '../api/client'
import { formatBytes } from '../hooks/useElapsed'

interface Props {
  dataset: DatasetInfo | null
  onUploaded: (dataset: DatasetInfo) => void
  disabled: boolean
}

const MAX_CLIENT_BYTES = 200 * 1024 * 1024

function UploadPanelImpl({ dataset, onUploaded, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | undefined>()

  const handleFile = useCallback(
    async (file: File) => {
      setError(undefined)

      // Fail fast on the client so an obviously wrong file does not consume a
      // 20 MB upload before the server rejects it.
      if (!file.name.toLowerCase().endsWith('.csv')) {
        setError(`"${file.name}" is not a .csv file.`)
        return
      }
      if (file.size === 0) {
        setError('That file is empty.')
        return
      }
      if (file.size > MAX_CLIENT_BYTES) {
        setError(
          `That file is ${formatBytes(file.size)}; the limit is ${formatBytes(MAX_CLIENT_BYTES)}.`,
        )
        return
      }

      setUploading(true)
      setProgress(0)
      try {
        const info = await uploadDataset(file, setProgress)
        onUploaded(info)
      } catch (uploadError) {
        setError(
          uploadError instanceof ApiError
            ? uploadError.message
            : uploadError instanceof Error
              ? uploadError.message
              : 'Upload failed.',
        )
      } finally {
        setUploading(false)
      }
    },
    [onUploaded],
  )

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      setDragging(false)
      if (disabled || uploading) return
      const file = event.dataTransfer.files?.[0]
      if (file) void handleFile(file)
    },
    [disabled, uploading, handleFile],
  )

  return (
    <section className="card upload">
      <div>
        <div
          className={`dropzone${dragging ? ' dropzone--active' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            if (!disabled && !uploading) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          {uploading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <strong>Uploading… {Math.round(progress * 100)}%</strong>
              <div className="progressbar" style={{ maxWidth: 200 }}>
                <div
                  className="progressbar__fill"
                  style={{ width: `${Math.round(progress * 100)}%` }}
                />
              </div>
            </>
          ) : (
            <>
              <strong style={{ fontSize: 13.5 }}>Drop a CSV here</strong>
              <span className="dropzone__hint">or</span>
              <button
                type="button"
                className="btn"
                onClick={() => inputRef.current?.click()}
                disabled={disabled}
              >
                Choose a file
              </button>
              <span className="dropzone__hint">
                .csv up to {formatBytes(MAX_CLIENT_BYTES)}
              </span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void handleFile(file)
              // Reset so re-picking the same file still fires onChange.
              event.target.value = ''
            }}
          />
        </div>

        {error && (
          <div className="alert" style={{ marginTop: 12 }} role="alert">
            <span aria-hidden="true">✕</span>
            <span>{error}</span>
          </div>
        )}
      </div>

      <div style={{ minWidth: 0 }}>
        {dataset ? (
          <>
            <div className="datasetmeta">
              <span className="badge badge--accent">{dataset.filename}</span>
              <span className="badge">{formatBytes(dataset.bytes)}</span>
              {dataset.rows !== null && (
                <span className="badge">{dataset.rows.toLocaleString()} rows</span>
              )}
              {dataset.columns !== null && (
                <span className="badge">{dataset.columns} columns</span>
              )}
              <span className="badge badge--mono">{dataset.dataset_id}</span>
            </div>
            <details className="disclosure">
              <summary>Dataset profile — exactly what the agents will be shown</summary>
              <div className="disclosure__body">
                <pre className="pre">{dataset.profile}</pre>
              </div>
            </details>
          </>
        ) : (
          <div className="empty" style={{ padding: '30px 16px' }}>
            Upload a CSV to see its schema, null counts and head preview before
            starting a run.
          </div>
        )}
      </div>
    </section>
  )
}

export const UploadPanel = memo(UploadPanelImpl)
