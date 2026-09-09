/**
 * Pure date arithmetic behind the graph's 3-week window picker.
 *
 * Dates are plain `YYYY-MM-DD` strings throughout — what the API sends and
 * expects — parsed as local midnight so a week boundary lands on the same
 * calendar day everywhere the app runs, not fifteen ways depending on the
 * reader's time zone offset.
 */

const MS_PER_DAY = 24 * 60 * 60 * 1000

function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1)
}

function toIsoDate(date: Date): string {
  const year = String(date.getFullYear()).padStart(4, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Today, as the same `YYYY-MM-DD` string the API speaks.
 *
 *  Local, not UTC: the reader's "today" is the one on their own calendar, and
 *  `toISOString().slice(0, 10)` reports yesterday for anyone west of Greenwich
 *  for part of their day.
 */
export function today(): string {
  return toIsoDate(new Date())
}

export function addDays(iso: string, days: number): string {
  const date = parseIsoDate(iso)
  date.setDate(date.getDate() + days)
  return toIsoDate(date)
}

/** The first of the month `months` away from `iso`'s. Lands on the 1st
 *  rather than carrying `iso`'s own day-of-month across, which is what makes
 *  this safe to apply repeatedly — a day-preserving `setMonth` skips or
 *  repeats months once the source day doesn't exist in the target one (31
 *  July + 1 month is 31 August, but 31 August + 1 month rolls over to 1
 *  October, having skipped September entirely). */
export function shiftMonth(iso: string, months: number): string {
  const date = parseIsoDate(iso)
  return toIsoDate(new Date(date.getFullYear(), date.getMonth() + months, 1))
}

/** `iso`'s own year and month, as `monthGrid`/`monthLabel` take them. */
export function monthOf(iso: string): { year: number; month: number } {
  const date = parseIsoDate(iso)
  return { year: date.getFullYear(), month: date.getMonth() }
}

/** `YYYY-MM`, for comparing two dates by month regardless of day. */
export function monthKey(iso: string): string {
  return iso.slice(0, 7)
}

/** Whole calendar days between two dates, `b - a`. Ignores time of day. */
export function daysBetween(a: string, b: string): number {
  return Math.round((parseIsoDate(b).getTime() - parseIsoDate(a).getTime()) / MS_PER_DAY)
}

const SHORT_DATE = { month: 'short', day: 'numeric' } as const

/** Three whole weeks: the centre's week, plus one either side. */
const WINDOW_DAYS = 21

/** The Monday of `iso`'s week.
 *
 *  Monday because that is where the API's weeks begin, so this is the same
 *  boundary the graph's points are bucketed on. `getDay()` counts from Sunday,
 *  hence the shift.
 */
function mondayOf(iso: string): string {
  const date = parseIsoDate(iso)
  return addDays(iso, -((date.getDay() + 6) % 7))
}

/**
 * "Aug 24 – Sep 13, 2026": the three whole weeks the graph plots.
 *
 * Anchored on week boundaries rather than measured out from `center` itself.
 * Two things were wrong with the latter. It ran centre-7 to centre+7, which
 * stopped on the *first* day of the third week and so named a 15-day span for
 * a period that is 21 days long — the label said "Aug 24 – Sep 7" while the
 * chart drew Aug 24, Aug 31 and Sep 7, that last week running to the 13th. And
 * with a centre that is not a Monday — the calendar lets any day be picked —
 * it named a span offset from the weeks actually drawn.
 *
 * Both years are named when the window crosses a year boundary. Naming only
 * the end year, as this once did, reads as though the whole window were in it.
 */
export function formatWeekRange(center: string): string {
  const start = mondayOf(addDays(center, -7))
  const end = addDays(start, WINDOW_DAYS - 1)
  const from = parseIsoDate(start)
  const to = parseIsoDate(end)
  const fromLabel = from.toLocaleDateString('en-US', SHORT_DATE)
  const toLabel = to.toLocaleDateString('en-US', SHORT_DATE)
  return from.getFullYear() === to.getFullYear()
    ? `${fromLabel} – ${toLabel}, ${String(to.getFullYear())}`
    : `${fromLabel}, ${String(from.getFullYear())} – ${toLabel}, ${String(to.getFullYear())}`
}

export interface CalendarDay {
  readonly iso: string
  readonly day: number
  /** Falsy for the leading/trailing days of neighbouring months that fill
   *  out the grid — shown muted, since the grid is always a whole number of
   *  weeks but the month it is naming is not. */
  readonly inMonth: boolean
}

/**
 * A Sunday-first 6-week grid (42 days) covering the given month, plus enough
 * of its neighbours to fill the grid. Always six weeks rather than however
 * many the month needs, so picking a different month does not reflow the
 * popover's height under the reader's cursor.
 */
export function monthGrid(year: number, month: number): CalendarDay[] {
  const firstOfMonth = new Date(year, month, 1)
  const start = new Date(year, month, 1 - firstOfMonth.getDay())
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start)
    date.setDate(start.getDate() + index)
    return { iso: toIsoDate(date), day: date.getDate(), inMonth: date.getMonth() === month }
  })
}

export function monthLabel(year: number, month: number): string {
  return new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

/** "September 6, 2026" — the day number alone repeats across a six-week grid
 *  (a neighbouring month's padding days reuse the same numbers), so a day
 *  cell needs the full date as its accessible name, not just its digits. */
export function dayLabel(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}
