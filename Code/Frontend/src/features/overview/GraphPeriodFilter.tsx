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

import { useEffect, useRef, useState } from 'react'

import { cx } from '@/shared/ui/cx'
import {
  addDays,
  dayLabel,
  daysBetween,
  formatWeekRange,
  monthGrid,
  monthKey,
  monthLabel,
  monthOf,
  shiftMonth,
} from './weekWindow'
import styles from './GraphPeriodFilter.module.css'

export type GraphFilterMode = 'week' | 'month'

const WEEKDAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
const WINDOW_HALF_WIDTH_DAYS = 7
const WEEK_NAV_SHIFT_DAYS = 14

function CalendarGlyph() {
  return (
    <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="12" rx="1.5" fill="none" stroke="currentColor" />
      <line x1="1.5" y1="6" x2="14.5" y2="6" stroke="currentColor" />
      <line x1="4.5" y1="1" x2="4.5" y2="3.5" stroke="currentColor" />
      <line x1="11.5" y1="1" x2="11.5" y2="3.5" stroke="currentColor" />
    </svg>
  )
}

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
  const [open, setOpen] = useState(false)
  const [visible, setVisible] = useState(() => monthOf(value))
  const wrapper = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const onClick = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('click', onClick)
    }
  }, [open])

  const openAtValue = () => {
    setVisible(monthOf(value))
    setOpen(true)
  }

  const browseMonth = (delta: number) => {
    setVisible(({ year, month }) => {
      const date = new Date(year, month + delta, 1)
      return { year: date.getFullYear(), month: date.getMonth() }
    })
  }

  const shiftSelection = (direction: -1 | 1) => {
    onChange(
      mode === 'month'
        ? shiftMonth(value, direction)
        : addDays(value, direction * WEEK_NAV_SHIFT_DAYS),
    )
  }

  return (
    <div className={styles.wrap} ref={wrapper}>
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
        <button
          type="button"
          className={styles.rangeButton}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => {
            if (open) {
              setOpen(false)
            } else {
              openAtValue()
            }
          }}
        >
          <CalendarGlyph />
          {mode === 'month'
            ? monthLabel(monthOf(value).year, monthOf(value).month)
            : formatWeekRange(value)}
        </button>
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

      {open ? (
        <div
          className={styles.popover}
          role="dialog"
          aria-label={mode === 'month' ? "Choose the month" : "Choose the window's centre week"}
        >
          <div className={styles.popoverHeader}>
            <button
              type="button"
              className={styles.navButton}
              aria-label="Previous month"
              onClick={() => {
                browseMonth(-1)
              }}
            >
              ‹
            </button>
            <b>{monthLabel(visible.year, visible.month)}</b>
            <button
              type="button"
              className={styles.navButton}
              aria-label="Next month"
              onClick={() => {
                browseMonth(1)
              }}
            >
              ›
            </button>
          </div>

          <div className={styles.weekdays}>
            {WEEKDAY_LABELS.map((label, index) => (
              // The two Sundays and two Tuesdays repeat, so the column index
              // is the only stable identity a header cell has.
              <span key={`${label}-${String(index)}`}>{label}</span>
            ))}
          </div>

          <div className={styles.days}>
            {monthGrid(visible.year, visible.month).map((cell) => {
              const isCentre = mode === 'week' && daysBetween(value, cell.iso) === 0
              const inWindow =
                mode === 'week'
                  ? !isCentre && Math.abs(daysBetween(value, cell.iso)) <= WINDOW_HALF_WIDTH_DAYS
                  : monthKey(cell.iso) === monthKey(value)
              return (
                <button
                  key={cell.iso}
                  type="button"
                  className={cx(
                    styles.day,
                    !cell.inMonth && styles.dayOutsideMonth,
                    inWindow && styles.dayInWindow,
                    isCentre && styles.dayCentre,
                  )}
                  aria-label={dayLabel(cell.iso)}
                  aria-current={isCentre ? 'date' : undefined}
                  onClick={() => {
                    onChange(cell.iso)
                    setOpen(false)
                  }}
                >
                  {cell.day}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
