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

/** "Sep 7 – Sep 21, 2026": the 15-day window centred on `center`. */
export function formatWeekRange(center: string): string {
  const start = parseIsoDate(addDays(center, -7))
  const end = parseIsoDate(addDays(center, 7))
  const year = end.getFullYear()
  return `${start.toLocaleDateString('en-US', SHORT_DATE)} – ${end.toLocaleDateString('en-US', SHORT_DATE)}, ${String(year)}`
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
