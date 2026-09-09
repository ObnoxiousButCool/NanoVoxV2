/**
 * The week/month picker that drives the dashboard's period.
 *
 * Emits an `anchor` — a date inside the chosen period — rather than an index,
 * because that is what the API accepts: the date to end the window on.
 *
 * Picking a month used to resolve to that month's *last week* and leave the
 * period weekly, so "September" reported one week of September: 11 calls out
 * of the month's 89, over a delta still captioned "on last week". A month now
 * emits the month itself and the caller asks the API to bucket by month, so
 * every figure is counted over the month's own calls.
 *
 * The months offered are the ones that contain a call, which is not the same
 * as the months the available weeks start in: a week starting 31 August whose
 * calls all fall in September makes August look populated when nothing was
 * placed in it, and picking it would draw an empty strip.
 */

import { useMemo, useState } from 'react'

import styles from './PeriodFilter.module.css'

export type Granularity = 'week' | 'month'

/**
 * The mode the dashboard opens in, shared so the filter's own state and the
 * page's cannot drift apart.
 *
 * Month rather than Week. Until a period is picked, week mode sent no period
 * at all to the card endpoints, and they read that as the whole corpus -- so
 * the screen opened with the top strip on a single week and every other card
 * on every call ever analysed, under a filter already naming that week.
 * Opening in Month gives the default a period the cards actually request, so
 * the screen agrees with itself on first paint, and it lands on the fullest
 * view rather than on whichever week happens to be last (often the thinnest,
 * being a partial one).
 */
export const DEFAULT_GRANULARITY: Granularity = 'month'

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

export function PeriodFilter({
  availableWeeks,
  availableMonths,
  anchor,
  onChange,
  onGranularityChange,
}: {
  /** Every week the corpus spans, oldest first. */
  availableWeeks: readonly string[]
  /** Every month that contains a call, oldest first, as first-of-month dates. */
  availableMonths: readonly string[]
  /** The currently selected anchor, or `undefined` for the latest window. */
  anchor: string | undefined
  onChange: (anchor: string | undefined) => void
  /** Fires whenever the Week/Month toggle itself changes — not on every
   *  render — for a caller that needs to know which mode this filter is in
   *  without owning it. The graph's own filter reads this once, to seed its
   *  starting mode; this filter's own Week/Month state stays internal. */
  onGranularityChange?: (granularity: Granularity) => void
}) {
  const [granularity, setGranularityState] = useState<Granularity>(DEFAULT_GRANULARITY)
  const setGranularity = (next: Granularity) => {
    setGranularityState(next)
    // Back to the latest period. The two modes emit different kinds of date —
    // a Monday and a first-of-month — so carrying one over leaves the other
    // dropdown displaying a value it has no option for.
    onChange(undefined)
    onGranularityChange?.(next)
  }

  const months = useMemo(() => availableMonths.map(monthKey), [availableMonths])

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
              const target = `${event.target.value}-01`
              onChange(monthKey(target) === latestMonth ? undefined : target)
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
