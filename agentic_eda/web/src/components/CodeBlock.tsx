/** Syntax-highlighted, collapsible view of agent-generated Python. */

import { Highlight, themes } from 'prism-react-renderer'
import { memo, useState } from 'react'

interface Props {
  code: string
  language?: string
  revision?: number
  /** Collapsed by default — generated scripts run to a few KB. */
  defaultOpen?: boolean
}

function CodeBlockImpl({ code, language = 'python', revision, defaultOpen = false }: Props) {
  const [copied, setCopied] = useState(false)

  const copy = async (event: React.MouseEvent) => {
    // Inside a <summary>, so stop the click from toggling the disclosure.
    event.preventDefault()
    event.stopPropagation()
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  const sizeLabel = `${(code.length / 1024).toFixed(1)} KB`
  const lineCount = code.split('\n').length

  return (
    <details className="disclosure" open={defaultOpen}>
      <summary>
        <span>Generated {language} code</span>
        <span className="badge badge--mono">{sizeLabel}</span>
        <span className="badge badge--mono">{lineCount} lines</span>
        {revision !== undefined && revision > 0 && (
          <span className="badge badge--warn">revision {revision}</span>
        )}
        <span style={{ flex: 1 }} />
        <button type="button" className="btn btn--ghost btn--sm" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </summary>
      <div className="disclosure__body">
        <Highlight code={code.trimEnd()} language={language} theme={themes.vsDark}>
          {({ tokens, getLineProps, getTokenProps, style }) => (
            <pre className="codeblock" style={{ ...style, background: 'var(--bg)' }}>
              {tokens.map((line, lineIndex) => {
                const { key: _lineKey, ...lineProps } = getLineProps({ line })
                return (
                  <div key={lineIndex} {...lineProps} className="codeblock__line">
                    <span className="codeblock__lineno">{lineIndex + 1}</span>
                    <span className="codeblock__content">
                      {line.map((token, tokenIndex) => {
                        const { key: _tokenKey, ...tokenProps } = getTokenProps({ token })
                        return <span key={tokenIndex} {...tokenProps} />
                      })}
                    </span>
                  </div>
                )
              })}
            </pre>
          )}
        </Highlight>
      </div>
    </details>
  )
}

export const CodeBlock = memo(CodeBlockImpl)
