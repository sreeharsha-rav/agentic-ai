/**
 * Client-side ticking clocks.
 *
 * These exist because the pipeline goes quiet for long stretches — the
 * multivariate stage can spend four minutes inside a single LLM call. If every
 * moving element on screen waited for a server event, the UI would look frozen
 * exactly when the user most needs reassurance. So elapsed time is computed
 * locally and ticks regardless of stream activity.
 */

import { useEffect, useState } from 'react'

/** Re-render on an interval, but only while `active`. */
export function useTicker(active: boolean, intervalMs = 1000): number {
  const [tick, setTick] = useState(() => Date.now())

  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setTick(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [active, intervalMs])

  return tick
}

/** Seconds since `startedAt`, live while `active`. */
export function useElapsedSeconds(
  startedAt: number | undefined,
  active: boolean,
  frozenSeconds?: number,
): number {
  const tick = useTicker(active)

  if (frozenSeconds !== undefined) return frozenSeconds
  if (startedAt === undefined) return 0

  const reference = active ? tick : Date.now()
  return Math.max(0, (reference - startedAt) / 1000)
}

/** `1m 18s` / `42s` — compact enough for a timeline chip. */
export function formatDuration(seconds: number | undefined): string {
  if (seconds === undefined || Number.isNaN(seconds)) return '—'
  const total = Math.max(0, Math.round(seconds))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  const remainder = total % 60
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`
}
