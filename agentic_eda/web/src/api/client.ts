/** REST calls against the FastAPI backend. Vite proxies /api, so paths are relative. */

import type { RunMode, RunStatus, StageId, StageStatus } from '../types/events'
import type { Artifact, ReasoningStep, PlanItem, RetryInfo } from '../types/events'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI reports errors as `{detail: string | ValidationError[]}`. */
async function toApiError(response: Response): Promise<ApiError> {
  let detail = response.statusText
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') {
      detail = body.detail
    } else if (Array.isArray(body?.detail)) {
      detail = body.detail.map((item: { msg?: string }) => item.msg ?? '').join('; ')
    }
  } catch {
    // Non-JSON error body; the status text is the best we have.
  }
  return new ApiError(detail, response.status)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    throw await toApiError(response)
  }
  return response.json() as Promise<T>
}

// --------------------------------------------------------------------------- //
// Datasets
// --------------------------------------------------------------------------- //

export interface DatasetInfo {
  dataset_id: string
  filename: string
  bytes: number
  uploaded_at: string
  profile: string
  rows: number | null
  columns: number | null
}

export interface DatasetSummary {
  dataset_id: string
  filename: string
  bytes: number
  uploaded_at: string
}

/**
 * Upload a CSV.
 *
 * Uses XMLHttpRequest rather than fetch purely for `upload.onprogress` — these
 * files run to tens of megabytes and a silent multi-second upload looks broken.
 */
export function uploadDataset(
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<DatasetInfo> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/datasets')

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(event.loaded / event.total)
      }
    }

    xhr.onload = () => {
      let body: unknown
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DatasetInfo)
        return
      }

      const detail =
        (body as { detail?: string } | null)?.detail ?? xhr.statusText ?? 'Upload failed'
      reject(new ApiError(String(detail), xhr.status))
    }

    xhr.onerror = () => reject(new ApiError('Network error during upload', 0))
    xhr.onabort = () => reject(new ApiError('Upload cancelled', 0))
    xhr.send(form)
  })
}

export function listDatasets(): Promise<DatasetSummary[]> {
  return request<DatasetSummary[]>('/api/datasets')
}

// --------------------------------------------------------------------------- //
// Runs
// --------------------------------------------------------------------------- //

export interface CreateRunResponse {
  run_id: string
  status: RunStatus
  mode: RunMode
  events_url: string
}

export interface StageSnapshot {
  id: StageId
  label: string
  status: StageStatus
  expected_seconds: number
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  progress: string | null
  turn: number | null
  turn_of: number | null
  reasoning: ReasoningStep[]
  plan_kind: 'variable' | 'relationship' | null
  plan_items: PlanItem[]
  code: string | null
  profiles: Record<string, string>
  turns: Record<string, unknown>
  retries: RetryInfo[]
  artifacts: Artifact[]
  summary: string | null
  error: string | null
}

export interface RunSnapshot {
  run_id: string
  status: RunStatus
  mode: RunMode
  dataset_name: string
  dataset_id: string | null
  created_at: string
  completed_at: string | null
  duration_seconds: number | null
  replay_of: string | null
  stage_order: StageId[]
  stages: Record<StageId, StageSnapshot>
  report_url: string | null
  error: string | null
  last_seq: number
  last_event_at: string | null
}

export interface RunSummaryInfo {
  run_id: string
  status: RunStatus
  mode: RunMode
  dataset_name: string
  dataset_id: string | null
  created_at: string
  completed_at: string | null
  duration_seconds: number | null
  chart_count: number
  replay_of: string | null
}

export interface ReportPayload {
  run_id: string
  markdown: string
  base_url: string
  url: string
}

export function createRun(datasetId: string): Promise<CreateRunResponse> {
  return request<CreateRunResponse>('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, mode: 'live' }),
  })
}

export function createReplayRun(sourceRunId: string): Promise<CreateRunResponse> {
  return request<CreateRunResponse>('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'replay', source_run_id: sourceRunId }),
  })
}

export function getRun(runId: string): Promise<RunSnapshot> {
  return request<RunSnapshot>(`/api/runs/${runId}`)
}

export function listRuns(): Promise<RunSummaryInfo[]> {
  return request<RunSummaryInfo[]>('/api/runs')
}

export function cancelRun(runId: string): Promise<RunSnapshot> {
  return request<RunSnapshot>(`/api/runs/${runId}/cancel`, { method: 'POST' })
}

export function getReport(runId: string): Promise<ReportPayload> {
  return request<ReportPayload>(`/api/runs/${runId}/report`)
}

export interface HealthInfo {
  status: string
  openai_key_configured: boolean
  max_concurrent_runs: number
  active_runs: number
  artifacts_url_prefix: string
  heartbeat_seconds: number
}

export function getHealth(): Promise<HealthInfo> {
  return request<HealthInfo>('/api/health')
}
