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
import type { CallSummary, Taxonomy } from '@/shared/api/types'
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
  // Not sortable: the API sorts by the columns it has an index for, and a
  // member identifier is something you filter to, not order by.
  { label: 'Member', sort: null },
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

/**
 * The human label for a category code.
 *
 * The API sends the code — `claims_eob` — because the label is a property of the
 * taxonomy rather than of the call, and the taxonomy can be relabelled without
 * touching stored data. The Overview resolves it server-side; this page already
 * loads the taxonomy for its filter dropdown, so it resolves it here from the
 * same source rather than shipping a second copy on every row.
 *
 * Falls back to the code itself. An unknown code means the taxonomy changed
 * under stored calls, and showing `claims_eob` is more use than showing nothing.
 */
function categoryLabel(code: string, categories: Taxonomy['categories'] | undefined): string {
  return categories?.find((entry) => entry.code === code)?.label ?? code
}

function CallRow({
  call,
  categories,
}: {
  call: CallSummary
  categories: Taxonomy['categories'] | undefined
}) {
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
      <td>{categoryLabel(call.category, categories)}</td>
      <td>{call.agent_name ?? '—'}</td>
      <td className={styles.member}>
        {call.member_id ? (
          <Link className={styles.rowLink} to={`/calls?member=${encodeURIComponent(call.member_id)}`}>
            {/* Stacked rather than "Name (ID)" on one line: this column sits in
                an already-wide table, and one long string would either wrap
                mid-identifier or push the outcome and score off-screen. */}
            {call.member_name ? <span className={styles.memberName}>{call.member_name}</span> : null}
            <span className={styles.memberId}>{call.member_id}</span>
          </Link>
        ) : (
          '—'
        )}
      </td>
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
  // One member's calls, arrived at from the at-risk list.
  const member = searchParams.get('member')
  // A score band, arrived at from the histogram. Read as text and passed
  // through: the API validates the range, and inventing a number here to
  // recover from a malformed one would filter on something nobody asked for.
  const minScore = searchParams.get('min_score')
  const maxScore = searchParams.get('max_score')
  // Call reference on load, so a call is where it was last time. Severity
  // remains one press of the Score column away, and any sort survives in the
  // URL — this is only what an unsorted visit gets.
  const sort = (searchParams.get('sort') ?? 'reference') as CallSortKey
  // Newest first by default: a call history is read from the most recent end,
  // and the far end of fifty rows is not where anyone starts. An explicit
  // direction in the URL still wins, so a shared link keeps its order.
  const direction = searchParams.get('direction')
  const descending = direction === null ? true : direction === 'desc'

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
    ...(member ? { member } : {}),
    ...(minScore ? { min_score: Number(minScore) } : {}),
    ...(maxScore ? { max_score: Number(maxScore) } : {}),
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

  const scoreBand = minScore ?? maxScore ? `${minScore ?? '0'}–${maxScore ?? '100'}` : null

  const narrowed =
    activeFilters.length > 0 ||
    Boolean(agent || broker || category || resolution || signal || member || scoreBand)

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
        subtitle="In call order by default. Press a column to sort by it — Score surfaces the calls that need action first."
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
            {member ? (
              <Button className={styles.active} aria-pressed onClick={clearParam('member')}>
                Member: {member} &times;
              </Button>
            ) : null}
            {scoreBand ? (
              <Button
                className={styles.active}
                aria-pressed
                onClick={() => {
                  // Both halves of a band clear together: half a range is not a
                  // filter anyone chose.
                  setOffset(0)
                  const next = new URLSearchParams(searchParams)
                  next.delete('min_score')
                  next.delete('max_score')
                  setSearchParams(next, { replace: true })
                }}
              >
                Score: {scoreBand} &times;
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
                    <CallRow
                      key={call.id}
                      call={call}
                      categories={taxonomy.data?.categories}
                    />
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
