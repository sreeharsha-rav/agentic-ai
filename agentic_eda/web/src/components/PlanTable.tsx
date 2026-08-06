/**
 * The agent's per-variable / per-relationship decision table.
 *
 * The skipped rows are the point. On the sample dataset the multivariate agent
 * evaluates ~37 pairs and selects 8 — and the rationale for a rejection is often
 * the most interesting output in the whole run (it rejects `Order ID vs Month` at
 * r=+0.993 because an identifier correlating with a date part is an artefact of
 * row ordering, not a finding). So skipped rows stay visible and filterable
 * rather than being hidden.
 *
 * `meets_threshold` disagreeing with `selected` is called out explicitly, since
 * that disagreement is exactly where the agent exercised judgement.
 */

import { memo, useMemo, useState } from 'react'

import { isRelationshipPlan, type PlanItem, type RelationshipPlan, type VariablePlan } from '../types/events'

type SortMode = 'natural' | 'correlation'

interface Props {
  kind: 'variable' | 'relationship'
  items: PlanItem[]
}

function correlationClass(value: number | null): string {
  if (value === null) return 'plan__corr'
  return Math.abs(value) >= 0.3 ? 'plan__corr plan__corr--strong' : 'plan__corr'
}

function formatCorrelation(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return value >= 0 ? `+${value.toFixed(3)}` : value.toFixed(3)
}

function VariableRows({ items }: { items: VariablePlan[] }) {
  return (
    <>
      {items.map((item, index) => (
        <tr key={`${item.variable}-${index}`} className={item.selected ? '' : 'plan--skipped'}>
          <td>{item.selected ? <span aria-label="selected">✓</span> : <span aria-label="skipped">—</span>}</td>
          <td className="mono nowrap">{item.variable}</td>
          <td>
            <span className="badge badge--mono">{item.data_kind}</span>
          </td>
          <td className="nowrap">{item.chart_type}</td>
          <td className="plan__rationale">{item.rationale}</td>
        </tr>
      ))}
    </>
  )
}

function RelationshipRows({ items }: { items: RelationshipPlan[] }) {
  return (
    <>
      {items.map((item, index) => {
        // The agent overrode the raw threshold in one direction or the other.
        const judgement = item.meets_threshold !== item.selected
        const pair = item.variable_y
          ? `${item.variable_x} × ${item.variable_y}`
          : item.variable_x
        return (
          <tr key={`${pair}-${index}`} className={item.selected ? '' : 'plan--skipped'}>
            <td>{item.selected ? <span aria-label="selected">✓</span> : <span aria-label="skipped">—</span>}</td>
            <td className="mono nowrap">{pair}</td>
            <td className={correlationClass(item.correlation)}>
              {formatCorrelation(item.correlation)}
            </td>
            <td className="nowrap">{item.chart_type}</td>
            <td className="plan__rationale">
              {judgement && (
                <span className="badge badge--warn" style={{ marginRight: 6 }}>
                  {item.meets_threshold ? 'threshold overridden' : 'selected below threshold'}
                </span>
              )}
              {item.rationale}
            </td>
          </tr>
        )
      })}
    </>
  )
}

function PlanTableImpl({ kind, items }: Props) {
  const [selectedOnly, setSelectedOnly] = useState(false)
  const [sortMode, setSortMode] = useState<SortMode>('natural')

  const selectedCount = useMemo(() => items.filter((item) => item.selected).length, [items])

  const visible = useMemo(() => {
    let rows = selectedOnly ? items.filter((item) => item.selected) : [...items]
    if (sortMode === 'correlation' && kind === 'relationship') {
      rows = rows.sort((a, b) => {
        const left = isRelationshipPlan(a) ? Math.abs(a.correlation ?? -1) : -1
        const right = isRelationshipPlan(b) ? Math.abs(b.correlation ?? -1) : -1
        return right - left
      })
    }
    return rows
  }, [items, selectedOnly, sortMode, kind])

  if (items.length === 0) return null

  const isRelationship = kind === 'relationship'
  const label = isRelationship ? 'relationship plans' : 'variable plans'

  return (
    <details className="disclosure">
      <summary>
        <span>Agent {label}</span>
        <span className="badge">{items.length} evaluated</span>
        <span className="badge badge--success">{selectedCount} selected</span>
      </summary>
      <div className="disclosure__body">
        <div className="toolbar">
          <label>
            <input
              type="checkbox"
              checked={selectedOnly}
              onChange={(event) => setSelectedOnly(event.target.checked)}
            />
            Selected only
          </label>
          {isRelationship && (
            <label>
              <input
                type="checkbox"
                checked={sortMode === 'correlation'}
                onChange={(event) => setSortMode(event.target.checked ? 'correlation' : 'natural')}
              />
              Sort by |r|
            </label>
          )}
          <span className="faint">
            showing {visible.length} of {items.length}
          </span>
        </div>

        <div className="tablewrap">
          <table className="plan">
            <thead>
              <tr>
                <th scope="col">
                  <span className="sronly">Selected</span>
                </th>
                <th scope="col">{isRelationship ? 'Pair' : 'Variable'}</th>
                <th scope="col">{isRelationship ? '|r|' : 'Kind'}</th>
                <th scope="col">Chart</th>
                <th scope="col">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {isRelationship ? (
                <RelationshipRows items={visible as RelationshipPlan[]} />
              ) : (
                <VariableRows items={visible as VariablePlan[]} />
              )}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  )
}

export const PlanTable = memo(PlanTableImpl)
