/**
 * Run state, folded from the event stream.
 *
 * Two rules make this correct rather than merely working:
 *
 * 1. **Idempotence.** After a reconnect the server replays everything past
 *    `Last-Event-ID`, and a second browser tab replays the whole history. Any
 *    event with `seq <= lastSeq` is therefore dropped, so applying the same
 *    event twice can never duplicate a reasoning step or a chart tile.
 * 2. **Normalized, not raw.** The projected `stages` map is the source of truth
 *    for rendering. The raw event array is kept only as a capped ring buffer for
 *    the debug drawer, so a run emitting hundreds of events does not grow
 *    unboundedly or re-render the tree from a giant array.
 */

import {
  STAGE_EXPECTED_SECONDS,
  STAGE_LABELS,
  STAGE_ORDER,
  type Artifact,
  type EdaEvent,
  type PlanItem,
  type ReasoningStep,
  type RetryInfo,
  type RunMode,
  type RunStatus,
  type StageId,
  type StageStatus,
} from '../types/events'
import type { RunSnapshot } from '../api/client'

/** Keep the debug drawer bounded; the server holds the full log on disk. */
const MAX_EVENT_LOG = 400

export type ConnectionState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface StageState {
  id: StageId
  label: string
  status: StageStatus
  expectedSeconds: number
  /** Epoch ms, client-side — used for live elapsed timers. */
  startedAt?: number
  completedAt?: number
  durationSeconds?: number
  progress?: string
  turn?: number
  turnOf?: number
  reasoning: ReasoningStep[]
  planKind?: 'variable' | 'relationship'
  planItems: PlanItem[]
  code?: string
  codeRevision?: number
  profiles: Record<string, string>
  turns: Record<string, unknown>
  retries: RetryInfo[]
  artifacts: Artifact[]
  summary?: string
  error?: string
}

export interface LogEntry {
  seq: number
  ts: string
  type: string
  stage: StageId | null
  payload: unknown
}

export interface RunState {
  runId: string | null
  status: RunStatus | 'idle'
  mode: RunMode
  replayOf?: string
  datasetName?: string
  stageOrder: StageId[]
  stages: Record<StageId, StageState>
  /** Dedup cursor. Also the value sent back as Last-Event-ID on reconnect. */
  lastSeq: number
  /** Epoch ms of the last event of any kind, including heartbeats. */
  lastEventAt?: number
  runStartedAt?: number
  durationSeconds?: number
  connection: ConnectionState
  reportUrl?: string
  chartCount: number
  error?: string
  cancelled: boolean
  eventLog: LogEntry[]
}

function emptyStage(id: StageId): StageState {
  return {
    id,
    label: STAGE_LABELS[id],
    status: 'pending',
    expectedSeconds: STAGE_EXPECTED_SECONDS[id],
    reasoning: [],
    planItems: [],
    profiles: {},
    turns: {},
    retries: [],
    artifacts: [],
  }
}

export function initialRunState(): RunState {
  return {
    runId: null,
    status: 'idle',
    mode: 'live',
    stageOrder: [...STAGE_ORDER],
    stages: {
      data_prep: emptyStage('data_prep'),
      univariate: emptyStage('univariate'),
      multivariate: emptyStage('multivariate'),
      report: emptyStage('report'),
    },
    lastSeq: 0,
    connection: 'idle',
    chartCount: 0,
    cancelled: false,
    eventLog: [],
  }
}

export type RunAction =
  | { type: 'reset' }
  | { type: 'run/created'; runId: string; mode: RunMode; datasetName?: string }
  | { type: 'connection'; state: ConnectionState }
  | { type: 'event'; event: EdaEvent }
  | { type: 'snapshot'; snapshot: RunSnapshot }
  | { type: 'error'; message: string }

function parseTs(ts: string): number {
  const parsed = Date.parse(ts)
  return Number.isNaN(parsed) ? Date.now() : parsed
}

/** Replace one stage immutably, leaving the other three references untouched. */
function withStage(
  state: RunState,
  id: StageId,
  update: (stage: StageState) => StageState,
): RunState {
  const current = state.stages[id]
  if (!current) return state
  return { ...state, stages: { ...state.stages, [id]: update(current) } }
}

function appendLog(state: RunState, event: EdaEvent): LogEntry[] {
  const entry: LogEntry = {
    seq: event.seq,
    ts: event.ts,
    type: event.type,
    stage: event.stage,
    payload: event.payload,
  }
  const log = [entry, ...state.eventLog]
  return log.length > MAX_EVENT_LOG ? log.slice(0, MAX_EVENT_LOG) : log
}

function applyEvent(state: RunState, event: EdaEvent): RunState {
  // Heartbeats carry no state beyond liveness, and deliberately reuse the last
  // real seq so they never advance the dedup cursor.
  if (event.type === 'heartbeat') {
    return { ...state, lastEventAt: parseTs(event.ts) }
  }

  // The dedup guard. Replayed history and multi-tab subscriptions both land here.
  if (event.seq <= state.lastSeq) {
    return state
  }

  let next: RunState = {
    ...state,
    lastSeq: event.seq,
    lastEventAt: parseTs(event.ts),
    eventLog: appendLog(state, event),
  }

  const stageId = event.stage

  switch (event.type) {
    case 'run.started': {
      next.runId = event.payload.run_id ?? event.run_id
      next.status = 'running'
      next.mode = event.payload.mode ?? 'live'
      next.replayOf = event.payload.replay_of
      next.datasetName = event.payload.dataset_name
      next.runStartedAt = parseTs(event.ts)
      return next
    }

    case 'stage.started': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        status: 'running',
        startedAt: parseTs(event.ts),
        expectedSeconds: event.payload.expected_seconds ?? stage.expectedSeconds,
      }))
    }

    case 'stage.progress': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        progress: event.payload.message,
        turn: event.payload.turn,
        turnOf: event.payload.of,
      }))
    }

    case 'agent.profile': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        profiles: { ...stage.profiles, [event.payload.kind]: event.payload.text },
      }))
    }

    case 'agent.reasoning': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        reasoning: [
          ...stage.reasoning,
          {
            index: event.payload.index,
            phase: event.payload.phase,
            observation: event.payload.observation,
            action: event.payload.action,
          },
        ],
      }))
    }

    case 'agent.turn.completed': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        turns: { ...stage.turns, [event.payload.turn]: event.payload.data },
      }))
    }

    case 'agent.plan': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        planKind: event.payload.kind,
        planItems: event.payload.items ?? [],
      }))
    }

    case 'agent.code': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        code: event.payload.code,
        codeRevision: event.payload.revision,
      }))
    }

    case 'agent.retry': {
      if (!stageId) return next
      const { attempt, attempts, max_attempts, error, exhausted } = event.payload
      return withStage(next, stageId, (stage) => ({
        ...stage,
        retries: [
          ...stage.retries,
          {
            attempt: attempt ?? attempts ?? stage.retries.length + 1,
            max_attempts: max_attempts,
            error: error,
            exhausted: Boolean(exhausted),
          },
        ],
      }))
    }

    case 'artifact.created': {
      if (!stageId) return next
      const artifact: Artifact = {
        kind: event.payload.kind,
        filename: event.payload.filename,
        url: event.payload.url,
        bytes: event.payload.bytes,
      }
      if (artifact.kind === 'chart') {
        next.chartCount = next.chartCount + 1
      }
      return withStage(next, stageId, (stage) => ({
        ...stage,
        artifacts: [...stage.artifacts, artifact],
      }))
    }

    case 'stage.completed': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        status: 'completed',
        completedAt: parseTs(event.ts),
        durationSeconds: event.payload.duration_seconds,
        summary: event.payload.summary ?? stage.summary,
        progress: undefined,
        turn: undefined,
        turnOf: undefined,
      }))
    }

    case 'stage.failed': {
      if (!stageId) return next
      return withStage(next, stageId, (stage) => ({
        ...stage,
        status: 'failed',
        completedAt: parseTs(event.ts),
        durationSeconds: event.payload.duration_seconds,
        error: event.payload.error,
        progress: undefined,
      }))
    }

    case 'run.completed': {
      next.status = 'completed'
      next.durationSeconds = event.payload.duration_seconds
      next.reportUrl = event.payload.report_url ?? undefined
      next.chartCount = event.payload.chart_count ?? next.chartCount
      next.connection = 'closed'
      return next
    }

    case 'run.failed': {
      next.status = event.payload.cancelled ? 'cancelled' : 'failed'
      next.cancelled = Boolean(event.payload.cancelled)
      next.error = event.payload.error
      next.durationSeconds = event.payload.duration_seconds
      next.connection = 'closed'
      // A stage that was mid-flight when the run died should not be left looking
      // like it is still working.
      const failing = event.payload.stage
      if (failing && next.stages[failing]?.status === 'running') {
        next = withStage(next, failing, (stage) => ({
          ...stage,
          status: 'failed',
          error: stage.error ?? event.payload.error,
          progress: undefined,
        }))
      }
      return next
    }

    default:
      return next
  }
}

/**
 * Hydrate from a `GET /api/runs/{id}` snapshot.
 *
 * Used on page reload: cheaper and far less chatty than replaying the whole
 * event history, and it leaves `lastSeq` set so a subsequent subscription
 * resumes from exactly the right place.
 */
function applySnapshot(state: RunState, snapshot: RunSnapshot): RunState {
  const stages = {} as Record<StageId, StageState>
  let chartCount = 0

  for (const id of STAGE_ORDER) {
    const incoming = snapshot.stages?.[id]
    if (!incoming) {
      stages[id] = emptyStage(id)
      continue
    }
    chartCount += incoming.artifacts.filter((artifact) => artifact.kind === 'chart').length
    stages[id] = {
      id,
      label: incoming.label ?? STAGE_LABELS[id],
      status: incoming.status,
      expectedSeconds: incoming.expected_seconds ?? STAGE_EXPECTED_SECONDS[id],
      startedAt: incoming.started_at ? parseTs(incoming.started_at) : undefined,
      completedAt: incoming.completed_at ? parseTs(incoming.completed_at) : undefined,
      durationSeconds: incoming.duration_seconds ?? undefined,
      progress: incoming.progress ?? undefined,
      turn: incoming.turn ?? undefined,
      turnOf: incoming.turn_of ?? undefined,
      reasoning: incoming.reasoning ?? [],
      planKind: incoming.plan_kind ?? undefined,
      planItems: incoming.plan_items ?? [],
      code: incoming.code ?? undefined,
      profiles: incoming.profiles ?? {},
      turns: incoming.turns ?? {},
      retries: incoming.retries ?? [],
      artifacts: incoming.artifacts ?? [],
      summary: incoming.summary ?? undefined,
      error: incoming.error ?? undefined,
    }
  }

  return {
    ...state,
    runId: snapshot.run_id,
    status: snapshot.status,
    mode: snapshot.mode,
    replayOf: snapshot.replay_of ?? undefined,
    datasetName: snapshot.dataset_name,
    stageOrder: snapshot.stage_order ?? [...STAGE_ORDER],
    stages,
    lastSeq: snapshot.last_seq ?? 0,
    lastEventAt: snapshot.last_event_at ? parseTs(snapshot.last_event_at) : undefined,
    runStartedAt: snapshot.created_at ? parseTs(snapshot.created_at) : undefined,
    durationSeconds: snapshot.duration_seconds ?? undefined,
    reportUrl: snapshot.report_url ?? undefined,
    chartCount,
    error: snapshot.error ?? undefined,
    cancelled: snapshot.status === 'cancelled',
  }
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'reset':
      return initialRunState()

    case 'run/created':
      return {
        ...initialRunState(),
        runId: action.runId,
        mode: action.mode,
        datasetName: action.datasetName,
        status: 'pending',
        connection: 'connecting',
        runStartedAt: Date.now(),
      }

    case 'connection':
      return { ...state, connection: action.state }

    case 'event':
      return applyEvent(state, action.event)

    case 'snapshot':
      return applySnapshot(state, action.snapshot)

    case 'error':
      return { ...state, error: action.message, connection: 'closed' }

    default:
      return state
  }
}

// --------------------------------------------------------------------------- //
// Selectors
// --------------------------------------------------------------------------- //

export function activeStage(state: RunState): StageState | undefined {
  return state.stageOrder
    .map((id) => state.stages[id])
    .find((stage) => stage?.status === 'running')
}

export function allArtifacts(state: RunState, kind?: Artifact['kind']): Artifact[] {
  return state.stageOrder
    .flatMap((id) => state.stages[id]?.artifacts ?? [])
    .filter((artifact) => !kind || artifact.kind === kind)
}

export function isRunActive(state: RunState): boolean {
  return state.status === 'pending' || state.status === 'running'
}

export function completedStageCount(state: RunState): number {
  return state.stageOrder.filter((id) => state.stages[id]?.status === 'completed').length
}
