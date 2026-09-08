/**
 * The week/month picker that drives the dashboard's period.
 *
 * The corpus is bucketed into calendar weeks and stays that way: picking
 * "month" does not aggregate anything new, it just narrows which weeks the
 * dropdown offers and jumps the trailing window to end at the last one in
 * that month. Picking "week" offers every week directly.
 *
 * Emits an `anchor` — a week's starting date — rather than an index or a
 * granularity, because that is exactly what the API already accepts: the
 * date to end the trailing window on.
 */

import { useMemo, useState } from 'react'

import styles from './PeriodFilter.module.css'

export type Granularity = 'week' | 'month'

function monthKey(isoDate: string): string {
  return isoDate.slice(0, 7)
}

function monthLabel(isoDate: string): string {
  const [year, month] = isoDate.split('-')
  const date = new Date(Number(year), Number(month) - 1, 1)
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

function weekLabel(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`)
  return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
}

/** The latest week (by start date) whose month matches `month` (`YYYY-MM`). */
function lastWeekInMonth(weeks: readonly string[], month: string): string | undefined {
  return [...weeks].reverse().find((week) => monthKey(week) === month)
}

export function PeriodFilter({
  availableWeeks,
  anchor,
  onChange,
  onGranularityChange,
}: {
  /** Every week the corpus spans, oldest first. */
  availableWeeks: readonly string[]
  /** The currently selected anchor, or `undefined` for the latest window. */
  anchor: string | undefined
  onChange: (anchor: string | undefined) => void
  /** Fires whenever the Week/Month toggle itself changes — not on every
   *  render — for a caller that needs to know which mode this filter is in
   *  without owning it. The graph's own filter reads this once, to seed its
   *  starting mode; this filter's own Week/Month state stays internal. */
  onGranularityChange?: (granularity: Granularity) => void
}) {
  const [granularity, setGranularityState] = useState<Granularity>('week')
  const setGranularity = (next: Granularity) => {
    setGranularityState(next)
    onGranularityChange?.(next)
  }

  const months = useMemo(() => {
    const seen = new Set<string>()
    const ordered: string[] = []
    for (const week of availableWeeks) {
      const key = monthKey(week)
      if (!seen.has(key)) {
        seen.add(key)
        ordered.push(key)
      }
    }
    return ordered
  }, [availableWeeks])

  const weeksNewestFirst = useMemo(() => [...availableWeeks].reverse(), [availableWeeks])
  const monthsNewestFirst = useMemo(() => [...months].reverse(), [months])

  if (weeksNewestFirst.length === 0 || monthsNewestFirst.length === 0) {
    return null
  }
  // Destructured rather than indexed: both arrays were just confirmed
  // non-empty, and destructuring (unlike `arr[0]`) types the result as
  // `string` outright instead of `string | undefined`.
  const [latestWeek] = weeksNewestFirst
  const [latestMonth] = monthsNewestFirst

  return (
    <div className={styles.filters}>
      <label className={styles.dropdown}>
        <span className={styles.dropdownLabel}>View by</span>
        <select
          value={granularity}
          onChange={(event) => {
            setGranularity(event.target.value as Granularity)
          }}
        >
          <option value="week">Week</option>
          <option value="month">Month</option>
        </select>
      </label>

      {granularity === 'week' ? (
        <label className={styles.dropdown}>
          <span className={styles.dropdownLabel}>Week</span>
          <select
            value={anchor ?? latestWeek}
            onChange={(event) => {
              const value = event.target.value
              onChange(value === latestWeek ? undefined : value)
            }}
          >
            {weeksNewestFirst.map((week) => (
              <option key={week} value={week}>
                {weekLabel(week)}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className={styles.dropdown}>
          <span className={styles.dropdownLabel}>Month</span>
          <select
            value={anchor ? monthKey(anchor) : latestMonth}
            onChange={(event) => {
              const target = lastWeekInMonth(availableWeeks, event.target.value) ?? latestWeek
              onChange(target === latestWeek ? undefined : target)
            }}
          >
            {monthsNewestFirst.map((month) => (
              <option key={month} value={month}>
                {monthLabel(`${month}-01`)}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  )
}
