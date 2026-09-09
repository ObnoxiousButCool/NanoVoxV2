/**
 * The graph's own period control.
 *
 * Deliberately not the week/month dropdown the page header uses, even though
 * it now offers the same two modes. The header's picker chooses which week
 * ends a trailing window; this one either centres a 15-day window on a day —
 * the week before, the week in question, and the week after, so a reader can
 * see a move rather than a trailing run — or shows a whole calendar month at
 * once. The header seeds this control's starting value when it changes, but
 * the two are independent from then on: this is the graph's own choice.
 */

import { addDays, formatWeekRange, monthLabel, monthOf, shiftMonth } from './weekWindow'
import styles from './GraphPeriodFilter.module.css'

export type GraphFilterMode = 'week' | 'month'

const WEEK_NAV_SHIFT_DAYS = 14

export function GraphPeriodFilter({
  mode,
  onModeChange,
  value,
  onChange,
}: {
  mode: GraphFilterMode
  onModeChange: (mode: GraphFilterMode) => void
  /** Week mode: the day the 15-day window is centred on. Month mode: any day
   *  within the selected month — only its year and month are read. */
  value: string
  onChange: (value: string) => void
}) {
  const shiftSelection = (direction: -1 | 1) => {
    onChange(
      mode === 'month'
        ? shiftMonth(value, direction)
        : addDays(value, direction * WEEK_NAV_SHIFT_DAYS),
    )
  }

  return (
    <div className={styles.wrap}>
      <label className={styles.dropdown}>
        <span className={styles.dropdownLabel}>View by</span>
        <select
          value={mode}
          aria-label="View by"
          onChange={(event) => {
            onModeChange(event.target.value as GraphFilterMode)
          }}
        >
          <option value="week">3-week</option>
          <option value="month">Month</option>
        </select>
      </label>

      <div className={styles.nav}>
        <button
          type="button"
          className={styles.navButton}
          aria-label={
            mode === 'month' ? 'Shift to the previous month' : 'Shift the window back two weeks'
          }
          onClick={() => {
            shiftSelection(-1)
          }}
        >
          ‹
        </button>
        {/* A read-out, not a control. `status` so a reader on a screen reader
            hears the new period when a chevron moves it, rather than having to
            go looking for what changed. */}
        <span className={styles.range} role="status">
          {mode === 'month'
            ? monthLabel(monthOf(value).year, monthOf(value).month)
            : formatWeekRange(value)}
        </span>
        <button
          type="button"
          className={styles.navButton}
          aria-label={
            mode === 'month' ? 'Shift to the next month' : 'Shift the window forward two weeks'
          }
          onClick={() => {
            shiftSelection(1)
          }}
        >
          ›
        </button>
      </div>
    </div>
  )
}
