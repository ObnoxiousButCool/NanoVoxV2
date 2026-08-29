/**
 * Every analysed call, most urgent first.
 *
 * Sorted by severity by default — the prototype's stated rule, "the calls that
 * need action surface first". A withheld score outranks everything, then the
 * lowest scores. Any column can be sorted on instead, which is a choice the user
 * makes rather than a default the screen imposes.
 *
 * Every filter and the sort live in the URL rather than in component state, so a
 * narrowed view is linkable, survives a reload, and steps back with the browser.
 * Each narrows the query server-side, so the count beneath the table is the
 * number of matching calls rather than the size of the page.
 */

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAgents, useBrokers, useCalls, useTaxonomy } from '@/shared/api/queries'
import type { CallFilters, CallSortKey } from '@/shared/api/endpoints'
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

/** Columns the table can be ordered by, in the order they are drawn. */
const COLUMNS: readonly { readonly label: string; readonly sort: CallSortKey | null }[] = [
  { label: 'Call', sort: 'reference' },
  { label: 'Member issue', sort: null },
  { label: 'Category', sort: 'category' },
  { label: 'Agent', sort: 'agent' },
  { label: 'Outcome', sort: 'resolution' },
  { label: 'Score', sort: 'score' },
  { label: 'Signals', sort: null },
]

function SortableHeader({
  label,
  sort,
  active,
  descending,
  onSort,
}: {
  label: string
  sort: CallSortKey | null
  active: boolean
  descending: boolean
  onSort: (sort: CallSortKey) => void
}) {
  if (sort === null) {
    return <th>{label}</th>
  }

  return (
    <th aria-sort={active ? (descending ? 'descending' : 'ascending') : 'none'}>
      <button
        type="button"
        className={cx(styles.sortButton, active && styles.sortActive)}
        onClick={() => {
          onSort(sort)
        }}
      >
        {label}
        <span aria-hidden="true">{active ? (descending ? ' ↓' : ' ↑') : ''}</span>
      </button>
    </th>
  )
}

function Dropdown({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: readonly { readonly value: string; readonly label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <label className={styles.dropdown}>
      <span className={styles.dropdownLabel}>{label}</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value)
        }}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
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
  // Arrived from a chart: ?agent=Sarah narrows the table to that agent. It lives
  // in the URL rather than in state so the view is linkable and survives a
  // reload — the same reason the call detail pages are addressable.
  const [searchParams, setSearchParams] = useSearchParams()
  const taxonomy = useTaxonomy()
  const agents = useAgents()
  const brokers = useBrokers()

  // Every filter and the sort live in the URL: the view is then linkable, it
  // survives a reload, and the back button steps through it — which is what a
  // user filtering a table expects, and what component state cannot give them.
  const agent = searchParams.get('agent')
  const broker = searchParams.get('broker')
  const category = searchParams.get('category')
  const resolution = searchParams.get('resolution')
  const signal = searchParams.get('signal')
  const sort = (searchParams.get('sort') ?? 'severity') as CallSortKey
  const descending = searchParams.get('direction') === 'desc'

  const filters: CallFilters = QUICK_FILTERS.filter((filter) =>
    activeFilters.includes(filter.id),
  ).reduce<CallFilters>((combined, filter) => ({ ...combined, ...filter.filters }), {
    limit: PAGE_SIZE,
    offset,
    sort,
    direction: descending ? 'desc' : 'asc',
    ...(agent ? { agent } : {}),
    ...(broker ? { broker } : {}),
    ...(category ? { category } : {}),
    ...(resolution ? { resolution } : {}),
    ...(signal ? { signal } : {}),
  })

  const setParam = (name: string, value: string) => {
    setOffset(0)
    const next = new URLSearchParams(searchParams)
    if (value) {
      next.set(name, value)
    } else {
      next.delete(name)
    }
    setSearchParams(next, { replace: true })
  }

  const clearParam = (name: string) => () => {
    setParam(name, '')
  }

  const toggleSort = (column: CallSortKey) => {
    setOffset(0)
    const next = new URLSearchParams(searchParams)
    next.set('sort', column)
    // Re-pressing the active column flips it; a new column starts ascending, so
    // the direction never carries over from an unrelated column.
    next.set('direction', sort === column && !descending ? 'desc' : 'asc')
    setSearchParams(next, { replace: true })
  }

  const narrowed =
    activeFilters.length > 0 || Boolean(agent || broker || category || resolution || signal)

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
        subtitle="Severity first by default — the calls that need action surface without looking. Press a column to sort by it instead."
        actions={
          <div className={styles.filters}>
            <Dropdown
              label="Category"
              value={category ?? ''}
              options={(taxonomy.data?.categories ?? []).map((entry) => ({
                value: entry.code,
                label: entry.label,
              }))}
              onChange={(value) => {
                setParam('category', value)
              }}
            />
            <Dropdown
              label="Agent"
              value={agent ?? ''}
              options={(agents.data ?? []).map((entry) => ({
                value: entry.agent_name,
                label: entry.agent_name,
              }))}
              onChange={(value) => {
                setParam('agent', value)
              }}
            />
            <Dropdown
              label="Outcome"
              value={resolution ?? ''}
              options={(taxonomy.data?.resolutions ?? []).map((value) => ({
                value,
                label: value.replace(/_/g, ' '),
              }))}
              onChange={(value) => {
                setParam('resolution', value)
              }}
            />
            <Dropdown
              label="Signal"
              value={signal ?? ''}
              options={(taxonomy.data?.signal_types ?? []).map((entry) => ({
                value: entry.code,
                label: entry.label,
              }))}
              onChange={(value) => {
                setParam('signal', value)
              }}
            />
            <Dropdown
              label="Broker"
              value={broker ?? ''}
              options={(brokers.data ?? []).map((entry) => ({
                value: entry.broker_name,
                label: entry.broker_name,
              }))}
              onChange={(value) => {
                setParam('broker', value)
              }}
            />
            {agent ? (
              <Button className={styles.active} aria-pressed onClick={clearParam('agent')}>
                Agent: {agent} &times;
              </Button>
            ) : null}
            {broker ? (
              <Button className={styles.active} aria-pressed onClick={clearParam('broker')}>
                Broker: {broker} &times;
              </Button>
            ) : null}
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
            {narrowed
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
                    {COLUMNS.map((column) => (
                      <SortableHeader
                        key={column.label}
                        label={column.label}
                        sort={column.sort}
                        active={column.sort === sort}
                        descending={descending}
                        onSort={toggleSort}
                      />
                    ))}
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
                {narrowed ? ' matching' : ''} call
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
