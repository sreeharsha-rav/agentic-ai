/**
 * The wire protocol, mirrored from `agentic_eda/server/models/events.py`.
 *
 * Events are modelled as a discriminated union on `type` so the reducer's switch
 * is exhaustive and each branch gets a correctly narrowed payload. That matters
 * here more than usual: a mistyped payload field would show up as a silently
 * blank card four minutes into a paid run.
 */

export type StageId = 'data_prep' | 'univariate' | 'multivariate' | 'report'

export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type RunMode = 'live' | 'replay'

export type ArtifactKind = 'chart' | 'cleaned_csv' | 'report'

export const STAGE_ORDER: StageId[] = ['data_prep', 'univariate', 'multivariate', 'report']

export const STAGE_LABELS: Record<StageId, string> = {
  data_prep: 'Data Preparation',
  univariate: 'Univariate Analysis',
  multivariate: 'Multivariate Analysis',
  report: 'Report Synthesis',
}

/** Observed wall-clock on the sample dataset; used for honest progress bars. */
export const STAGE_EXPECTED_SECONDS: Record<StageId, number> = {
  data_prep: 50,
  univariate: 105,
  multivariate: 165,
  report: 150,
}

export const STAGE_BLURBS: Record<StageId, string> = {
  data_prep: 'Profiles the raw CSV, reasons about cleaning, then runs generated pandas code.',
  univariate: 'Two turns: picks a chart per column, then writes one matplotlib script.',
  multivariate: 'Two turns: correlation-driven relationship selection, then chart code.',
  report: 'Reads every generated chart with a vision model and writes the narrative.',
}

// --------------------------------------------------------------------------- //
// Agent output shapes
// --------------------------------------------------------------------------- //

export interface ReasoningStep {
  index: number
  phase: string
  observation: string
  action: string
}

export type DataKind =
  | 'numeric_continuous'
  | 'numeric_discrete'
  | 'categorical'
  | 'datetime_part'
  | 'identifier_skip'

export interface VariablePlan {
  variable: string
  data_kind: DataKind
  chart_type: string
  selected: boolean
  rationale: string
  output_filename: string
}

export type RelationshipType =
  | 'numeric_numeric'
  | 'numeric_categorical'
  | 'categorical_categorical_skip'
  | 'multiway_skip'

export interface RelationshipPlan {
  variable_x: string
  variable_y: string
  relationship_type: RelationshipType
  correlation: number | null
  meets_threshold: boolean
  selected: boolean
  chart_type: string
  rationale: string
  output_filename: string
}

export type PlanItem = VariablePlan | RelationshipPlan

export function isRelationshipPlan(item: PlanItem): item is RelationshipPlan {
  return 'variable_x' in item
}

export interface Artifact {
  kind: ArtifactKind
  filename: string
  url: string
  bytes: number | null
}

export interface RetryInfo {
  attempt: number
  max_attempts: number
  error: string
  exhausted: boolean
}

// --------------------------------------------------------------------------- //
// Event payloads
// --------------------------------------------------------------------------- //

export interface StageDescriptor {
  id: StageId
  label: string
  expected_seconds: number
}

interface Envelope<TType extends string, TPayload> {
  seq: number
  ts: string
  run_id: string
  type: TType
  stage: StageId | null
  payload: TPayload
}

export type RunStartedEvent = Envelope<
  'run.started',
  {
    run_id: string
    dataset_name: string
    dataset_file?: string
    mode: RunMode
    replay_of?: string
    stages: StageDescriptor[]
  }
>

export type StageStartedEvent = Envelope<
  'stage.started',
  { stage: StageId; label: string; expected_seconds: number }
>

export type StageProgressEvent = Envelope<
  'stage.progress',
  { message: string; turn?: number; of?: number }
>

export type AgentProfileEvent = Envelope<
  'agent.profile',
  { kind: 'dataset' | 'correlation'; text: string }
>

export type AgentReasoningEvent = Envelope<
  'agent.reasoning',
  { index: number; phase: string; observation: string; action: string }
>

export type AgentTurnCompletedEvent = Envelope<
  'agent.turn.completed',
  { turn: string; data: unknown }
>

export type AgentPlanEvent = Envelope<
  'agent.plan',
  { kind: 'variable' | 'relationship'; items: PlanItem[] }
>

export type AgentCodeEvent = Envelope<
  'agent.code',
  { language: string; code: string; revision?: number }
>

export type AgentRetryEvent = Envelope<
  'agent.retry',
  {
    attempt?: number
    attempts?: number
    max_attempts: number
    error: string
    exhausted?: boolean
  }
>

export type ArtifactCreatedEvent = Envelope<
  'artifact.created',
  { kind: ArtifactKind; filename: string; url: string; bytes: number | null }
>

export type StageCompletedEvent = Envelope<
  'stage.completed',
  {
    stage: StageId
    summary: string | null
    duration_seconds: number
    artifact_count: number
  }
>

export type StageFailedEvent = Envelope<
  'stage.failed',
  { stage: StageId; error: string; duration_seconds: number }
>

export type RunCompletedEvent = Envelope<
  'run.completed',
  {
    report_url: string | null
    report_filename?: string
    duration_seconds: number
    chart_count: number
  }
>

export type RunFailedEvent = Envelope<
  'run.failed',
  {
    stage: StageId | null
    error: string
    cancelled?: boolean
    duration_seconds: number
  }
>

export type HeartbeatEvent = Envelope<
  'heartbeat',
  { elapsed_seconds: number; active_stage: StageId | null; run_status: RunStatus }
>

export type EdaEvent =
  | RunStartedEvent
  | StageStartedEvent
  | StageProgressEvent
  | AgentProfileEvent
  | AgentReasoningEvent
  | AgentTurnCompletedEvent
  | AgentPlanEvent
  | AgentCodeEvent
  | AgentRetryEvent
  | ArtifactCreatedEvent
  | StageCompletedEvent
  | StageFailedEvent
  | RunCompletedEvent
  | RunFailedEvent
  | HeartbeatEvent

export type EdaEventType = EdaEvent['type']

export const TERMINAL_EVENT_TYPES: EdaEventType[] = ['run.completed', 'run.failed']

export function isTerminal(type: EdaEventType): boolean {
  return TERMINAL_EVENT_TYPES.includes(type)
}
