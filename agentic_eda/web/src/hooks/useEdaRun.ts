/**
 * Owns a run's lifecycle: trigger, subscribe, fold events, rehydrate.
 *
 * The important structural choice is that runs are created in an explicit user
 * action (`start` / `replay`), never inside an effect. Under React StrictMode
 * every effect body runs twice in development; if creation lived in an effect
 * that would fire two paid 4-12 minute pipelines per click. Subscription does
 * live in an effect — but subscribing is read-only and idempotent, so a double
 * mount merely opens a second stream that replays the same history, which the
 * reducer's seq guard discards.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import {
  ApiError,
  cancelRun as cancelRunRequest,
  createReplayRun,
  createRun,
  getRun,
} from '../api/client'
import { subscribeToRun, type EventStreamHandle } from '../api/eventStream'
import { initialRunState, isRunActive, runReducer, type RunState } from '../state/runReducer'

export interface UseEdaRun {
  state: RunState
  starting: boolean
  startError?: string
  start: (datasetId: string, datasetName?: string) => Promise<void>
  replay: (sourceRunId: string) => Promise<void>
  attach: (runId: string) => Promise<void>
  cancel: () => Promise<void>
  reset: () => void
}

export function useEdaRun(): UseEdaRun {
  const [state, dispatch] = useReducer(runReducer, undefined, initialRunState)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | undefined>()

  // The run we want a subscription for. Kept in state (not a ref) so the effect
  // below re-runs when it changes.
  const [subscribedRunId, setSubscribedRunId] = useState<string | null>(null)
  const streamRef = useRef<EventStreamHandle | null>(null)

  useEffect(() => {
    if (!subscribedRunId) return

    dispatch({ type: 'connection', state: 'connecting' })

    const handle = subscribeToRun(subscribedRunId, {
      onEvent: (event) => dispatch({ type: 'event', event }),
      onOpen: () => dispatch({ type: 'connection', state: 'open' }),
      onReconnecting: () => dispatch({ type: 'connection', state: 'reconnecting' }),
      onClose: () => dispatch({ type: 'connection', state: 'closed' }),
      onError: (message) => dispatch({ type: 'error', message }),
    })
    streamRef.current = handle

    return () => {
      handle.close()
      if (streamRef.current === handle) {
        streamRef.current = null
      }
    }
  }, [subscribedRunId])

  const beginRun = useCallback(
    async (
      create: () => Promise<{ run_id: string; mode: 'live' | 'replay' }>,
      datasetName?: string,
    ) => {
      setStarting(true)
      setStartError(undefined)
      try {
        const created = await create()
        dispatch({
          type: 'run/created',
          runId: created.run_id,
          mode: created.mode,
          datasetName,
        })
        setSubscribedRunId(created.run_id)
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : 'Could not start the run.'
        setStartError(message)
        throw error
      } finally {
        setStarting(false)
      }
    },
    [],
  )

  const start = useCallback(
    async (datasetId: string, datasetName?: string) => {
      await beginRun(() => createRun(datasetId), datasetName)
    },
    [beginRun],
  )

  const replay = useCallback(
    async (sourceRunId: string) => {
      await beginRun(() => createReplayRun(sourceRunId))
    },
    [beginRun],
  )

  /**
   * Rehydrate an existing run, then resume streaming.
   *
   * Snapshot first so a reloaded page paints complete state immediately; the
   * snapshot carries `last_seq`, so the reducer discards the history the server
   * replays on subscribe and only new events get applied.
   */
  const attach = useCallback(async (runId: string) => {
    setStartError(undefined)
    try {
      const snapshot = await getRun(runId)
      dispatch({ type: 'snapshot', snapshot })
      if (snapshot.status === 'pending' || snapshot.status === 'running') {
        setSubscribedRunId(runId)
      } else {
        dispatch({ type: 'connection', state: 'closed' })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load that run.'
      setStartError(message)
    }
  }, [])

  const cancel = useCallback(async () => {
    if (!state.runId) return
    try {
      await cancelRunRequest(state.runId)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not cancel the run.'
      setStartError(message)
    }
  }, [state.runId])

  const reset = useCallback(() => {
    streamRef.current?.close()
    streamRef.current = null
    setSubscribedRunId(null)
    setStartError(undefined)
    dispatch({ type: 'reset' })
  }, [])

  // Once a run reaches a terminal state there is nothing left to stream.
  useEffect(() => {
    if (subscribedRunId && !isRunActive(state) && state.status !== 'idle') {
      streamRef.current?.close()
    }
  }, [state.status, subscribedRunId, state])

  return { state, starting, startError, start, replay, attach, cancel, reset }
}
