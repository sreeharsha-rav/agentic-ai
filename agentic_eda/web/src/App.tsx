/**
 * Single scrolling page: upload → trigger → live stage timeline → report.
 *
 * One page rather than tabs, because attention moves across a run: first "is it
 * working" (the sticky timeline), then "what is it deciding" (stage cards), then
 * "what did it find" (charts and report). Tabs would hide the live timeline at
 * exactly the moment it is the thing the user wants to see.
 */

import { useCallback, useEffect, useState } from 'react'

import { getHealth, listRuns, type DatasetInfo, type RunSummaryInfo } from './api/client'
import { ConnectionStatus } from './components/ConnectionStatus'
import { EventLogDrawer } from './components/EventLogDrawer'
import { ReportViewer } from './components/ReportViewer'
import { RunControls } from './components/RunControls'
import { StageCard } from './components/StageCard'
import { StageTimeline } from './components/StageTimeline'
import { UploadPanel } from './components/UploadPanel'
import { useEdaRun } from './hooks/useEdaRun'
import { formatDuration } from './hooks/useElapsed'
import type { StageId } from './types/events'

/** Survives a page reload so a run in progress can be picked back up. */
const ACTIVE_RUN_KEY = 'agentic-eda:active-run'

export default function App() {
  const { state, starting, startError, start, replay, attach, cancel, reset } = useEdaRun()

  const [dataset, setDataset] = useState<DatasetInfo | null>(null)
  const [runs, setRuns] = useState<RunSummaryInfo[]>([])
  const [keyConfigured, setKeyConfigured] = useState(true)
  const [selectedStage, setSelectedStage] = useState<StageId | null>(null)

  // -- initial load: health, run list, and any run we were watching ---------- //
  useEffect(() => {
    void getHealth()
      .then((health) => setKeyConfigured(health.openai_key_configured))
      .catch(() => setKeyConfigured(true))

    void listRuns()
      .then(setRuns)
      .catch(() => setRuns([]))

    const previous = window.localStorage.getItem(ACTIVE_RUN_KEY)
    if (previous) {
      void attach(previous)
    }
  }, [attach])

  // -- remember / forget the run across reloads ----------------------------- //
  useEffect(() => {
    if (!state.runId) return
    if (state.status === 'pending' || state.status === 'running') {
      window.localStorage.setItem(ACTIVE_RUN_KEY, state.runId)
    } else {
      window.localStorage.removeItem(ACTIVE_RUN_KEY)
    }
  }, [state.runId, state.status])

  // -- refresh the replay list whenever a run finishes ---------------------- //
  useEffect(() => {
    if (state.status === 'completed' || state.status === 'failed') {
      void listRuns()
        .then(setRuns)
        .catch(() => undefined)
    }
  }, [state.status])

  const onStart = useCallback(() => {
    if (!dataset) return
    void start(dataset.dataset_id, dataset.filename).catch(() => undefined)
  }, [dataset, start])

  const onReplay = useCallback(
    (sourceRunId: string) => {
      void replay(sourceRunId).catch(() => undefined)
    },
    [replay],
  )

  const onReset = useCallback(() => {
    window.localStorage.removeItem(ACTIVE_RUN_KEY)
    setSelectedStage(null)
    reset()
  }, [reset])

  const onSelectStage = useCallback((id: StageId) => {
    setSelectedStage(id)
    document.getElementById(`stage-${id}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }, [])

  const showTimeline = state.status !== 'idle'
  const reportReady = state.status === 'completed' && Boolean(state.runId)

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__title">
          <h1>Agentic EDA</h1>
          <span className="topbar__subtitle">four LLM agents · streamed over SSE</span>
        </div>
        <div className="topbar__status">
          <ConnectionStatus state={state} />
        </div>
      </header>

      <section className="section">
        <div className="section__head">
          <h2>1 · Dataset</h2>
          {dataset && state.status === 'idle' && (
            <span className="faint" style={{ fontSize: 12 }}>
              Ready to analyse
            </span>
          )}
        </div>
        <UploadPanel
          dataset={dataset}
          onUploaded={setDataset}
          disabled={state.status === 'pending' || state.status === 'running'}
        />
      </section>

      <section className="section">
        <div className="section__head">
          <h2>2 · Run</h2>
        </div>
        <RunControls
          dataset={dataset}
          state={state}
          starting={starting}
          startError={startError}
          runs={runs}
          keyConfigured={keyConfigured}
          onStart={onStart}
          onReplay={onReplay}
          onCancel={() => void cancel()}
          onReset={onReset}
        />
      </section>

      {showTimeline && (
        <>
          <section className="section">
            <div className="section__head">
              <h2>3 · Pipeline</h2>
              <span className="faint" style={{ fontSize: 12 }}>
                {state.datasetName}
                {state.durationSeconds !== undefined &&
                  ` · total ${formatDuration(state.durationSeconds)}`}
              </span>
            </div>

            <StageTimeline state={state} selected={selectedStage} onSelect={onSelectStage} />

            {state.error && (
              <div className="alert" style={{ marginTop: 12 }} role="alert">
                <span aria-hidden="true">✕</span>
                <div>
                  <strong>{state.cancelled ? 'Run cancelled.' : 'Run failed.'}</strong>{' '}
                  {state.error}
                  <div className="faint" style={{ marginTop: 4, fontSize: 12 }}>
                    Output from stages that completed before the failure is preserved below.
                  </div>
                </div>
              </div>
            )}

            {state.stageOrder.map((id, index) => {
              const stage = state.stages[id]
              if (!stage) return null
              return (
                <div id={`stage-${id}`} key={id}>
                  <StageCard stage={stage} index={index} />
                </div>
              )
            })}
          </section>

          {reportReady && state.runId && (
            <section className="section">
              <div className="section__head">
                <h2>4 · Synthesized report</h2>
                <span className="faint" style={{ fontSize: 12 }}>
                  written from {state.chartCount} charts by a vision model
                </span>
              </div>
              <ReportViewer runId={state.runId} ready={reportReady} />
            </section>
          )}
        </>
      )}

      {!showTimeline && (
        <section className="section">
          <div className="card empty">
            Upload a CSV and press <strong>Start EDA run</strong> to watch the four agents
            work. Every reasoning step, generated script, chart and retry streams here live.
          </div>
        </section>
      )}

      <EventLogDrawer entries={state.eventLog} lastSeq={state.lastSeq} />
    </div>
  )
}
