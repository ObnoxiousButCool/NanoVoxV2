/**
 * Every analysed call, most urgent first.
 *
 * Sorted by severity rather than date — the prototype's stated rule, "the calls
 * that need action surface first". A withheld score outranks everything, then
 * the lowest scores.
 *
 * The filters are the prototype's three buttons made real. Each narrows the
 * query server-side, so the count beneath the table is the number of matching
 * calls rather than the size of the page.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useCalls } from '@/shared/api/queries'
import type { CallFilters } from '@/shared/api/endpoints'
import type { CallSummary } from '@/shared/api/types'
import { Button, Card, Chip, Empty, Failure, Loading, Note, PageHeader } from '@/shared/ui/primitives'
import { toneForResolution } from '@/shared/ui/tone'
import { cx } from '@/shared/ui/cx'
import styles from './CallsPage.module.css'

const PAGE_SIZE = 25
const LOW_SCORE_CEILING = 65

interface QuickFilter {
  readonly id: string
  readonly label: string
  readonly filters: CallFilters
}

const QUICK_FILTERS: readonly QuickFilter[] = [
  { id: 'unresolved', label: 'Unresolved only', filters: { resolution: 'UNRESOLVED' } },
  { id: 'low', label: `Score under ${String(LOW_SCORE_CEILING)}`, filters: { max_score: LOW_SCORE_CEILING - 1 } },
  { id: 'broker', label: 'Broker signal', filters: { has_broker_signal: true } },
  { id: 'clinical', label: 'Clinical risk', filters: { signal: 'clinical_risk' } },
]

function scoreClass(tier: string): string | undefined {
  if (tier === 'GOOD') return styles.scoreGood
  if (tier === 'AVERAGE') return styles.scoreAverage
  return styles.scorePoor
}

function CallRow({ call }: { call: CallSummary }) {
  return (
    <tr>
      <td className={styles.reference}>
        <Link className={styles.rowLink} to={`/calls/${String(call.id)}`}>
          {call.reference}
        </Link>
      </td>
      <td className={styles.issue}>
        <Link className={styles.rowLink} to={`/calls/${String(call.id)}`}>
          <b>{call.title}</b>
          <div className={styles.tiny}>{call.summary}</div>
        </Link>
      </td>
      <td>{call.category}</td>
      <td>{call.agent_name ?? '—'}</td>
      <td>
        <Chip tone={toneForResolution(call.resolution)}>{call.resolution}</Chip>
      </td>
      <td>
        <span className={cx(styles.score, scoreClass(call.tier))}>{call.score}</span>
        {call.score_status === 'provisional' ? (
          <span className={styles.provisional}>WITHHELD</span>
        ) : null}
      </td>
      <td>
        <div className={styles.signals}>
          {call.signal_codes.map((code) => (
            <Chip key={code} tone="high">
              {code.replace(/_/g, ' ')}
            </Chip>
          ))}
          {call.broker_names.map((name) => (
            <Chip key={name} tone="broker">
              {name}
            </Chip>
          ))}
        </div>
      </td>
    </tr>
  )
}

export function CallsPage() {
  const [activeFilters, setActiveFilters] = useState<readonly string[]>([])
  const [offset, setOffset] = useState(0)

  const filters: CallFilters = QUICK_FILTERS.filter((filter) =>
    activeFilters.includes(filter.id),
  ).reduce<CallFilters>((combined, filter) => ({ ...combined, ...filter.filters }), {
    limit: PAGE_SIZE,
    offset,
  })

  const { data, isPending, error } = useCalls(filters)

  const toggle = (id: string) => {
    setOffset(0)
    setActiveFilters((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  return (
    <>
      <PageHeader
        title="Calls"
        subtitle="Sorted by severity, not date — the calls that need action surface first."
        actions={
          <div className={styles.filters}>
            {QUICK_FILTERS.map((filter) => (
              <Button
                key={filter.id}
                className={activeFilters.includes(filter.id) ? styles.active : undefined}
                aria-pressed={activeFilters.includes(filter.id)}
                onClick={() => {
                  toggle(filter.id)
                }}
              >
                {filter.label}
              </Button>
            ))}
          </div>
        }
      />

      <Card>
        {isPending ? <Loading what="calls" /> : null}
        {error ? <Failure error={error} what="the call list" /> : null}
        {data && data.items.length === 0 ? (
          <Empty title="No calls match">
            {activeFilters.length > 0
              ? 'Clear a filter to widen the search.'
              : 'Nothing has been analysed yet.'}
          </Empty>
        ) : null}
        {data && data.items.length > 0 ? (
          <>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Call</th>
                    <th>Member issue</th>
                    <th>Category</th>
                    <th>Agent</th>
                    <th>Outcome</th>
                    <th>Score</th>
                    <th>Signals</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((call) => (
                    <CallRow key={call.id} call={call} />
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.pager}>
              <Note>
                Showing {data.offset + 1}–{data.offset + data.items.length} of {data.total}
                {activeFilters.length > 0 ? ' matching' : ''} call
                {data.total === 1 ? '' : 's'}.
              </Note>
              <div className={styles.pagerButtons}>
                <Button
                  disabled={data.offset === 0}
                  onClick={() => {
                    setOffset(Math.max(data.offset - PAGE_SIZE, 0))
                  }}
                >
                  Previous
                </Button>
                <Button
                  disabled={!data.has_more}
                  onClick={() => {
                    setOffset(data.offset + PAGE_SIZE)
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </Card>
    </>
  )
}
