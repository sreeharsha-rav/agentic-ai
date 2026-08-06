/**
 * Surfaces a self-correction attempt.
 *
 * When generated matplotlib code fails, the agent is handed the traceback and
 * asked to fix it inside the same conversation. That is a designed capability,
 * not a malfunction, so a retry is presented as the agent working — amber and
 * explanatory. Only an *exhausted* retry budget turns red.
 */

import { memo } from 'react'

import type { RetryInfo } from '../types/events'

interface Props {
  retries: RetryInfo[]
}

function RetryBannerImpl({ retries }: Props) {
  if (retries.length === 0) return null

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {retries.map((retry, index) => (
        <div
          className={`retry${retry.exhausted ? ' retry--exhausted' : ''}`}
          key={`${retry.attempt}-${index}`}
          role={retry.exhausted ? 'alert' : 'status'}
        >
          <div className="retry__head">
            <span aria-hidden="true">{retry.exhausted ? '✕' : '⟳'}</span>
            {retry.exhausted ? (
              <>
                <span>Self-correction exhausted</span>
                <span className="retry__note">
                  after {retry.attempt} of {retry.max_attempts} attempts
                </span>
              </>
            ) : (
              <>
                <span>
                  Self-correcting — attempt {retry.attempt} of {retry.max_attempts}
                </span>
                <span className="retry__note">
                  the generated code failed; the traceback was fed back to the agent
                </span>
              </>
            )}
          </div>
          <details className="disclosure">
            <summary>Execution error</summary>
            <div className="disclosure__body">
              <pre className="pre">{retry.error}</pre>
            </div>
          </details>
        </div>
      ))}
    </div>
  )
}

export const RetryBanner = memo(RetryBannerImpl)
