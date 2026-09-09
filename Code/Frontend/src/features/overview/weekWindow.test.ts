import { describe, expect, it } from 'vitest'

import {
  addDays,
  daysBetween,
  formatWeekRange,
  monthGrid,
  monthKey,
  monthLabel,
  monthOf,
  pointRangeLabel,
  shiftMonth,
} from './weekWindow'

describe('addDays', () => {
  it('adds days within a month', () => {
    expect(addDays('2026-09-07', 7)).toBe('2026-09-14')
  })

  it('carries over a month boundary', () => {
    expect(addDays('2026-09-28', 7)).toBe('2026-10-05')
  })

  it('carries over a year boundary', () => {
    expect(addDays('2026-12-30', 7)).toBe('2027-01-06')
  })

  it('subtracts with a negative count', () => {
    expect(addDays('2026-09-14', -7)).toBe('2026-09-07')
  })
})

describe('daysBetween', () => {
  it('counts whole days regardless of order', () => {
    expect(daysBetween('2026-09-07', '2026-09-14')).toBe(7)
    expect(daysBetween('2026-09-14', '2026-09-07')).toBe(-7)
  })
})

describe('formatWeekRange', () => {
  it('spans a week either side of the centre', () => {
    expect(formatWeekRange('2026-09-14')).toBe('Sep 7 – Sep 21, 2026')
  })

  it('names the window\'s own year when the centre sits near a year boundary', () => {
    // The window itself (28 Dec - 11 Jan) crosses the boundary; the label
    // takes its year from where the window ends, not where it starts.
    expect(formatWeekRange('2027-01-04')).toBe('Dec 28 – Jan 11, 2027')
  })
})

describe('monthGrid', () => {
  it('always returns six full weeks', () => {
    const grid = monthGrid(2026, 8) // September 2026
    expect(grid).toHaveLength(42)
  })

  it('starts the grid on a Sunday', () => {
    const grid = monthGrid(2026, 8)
    expect(grid[0]?.iso).toBe('2026-08-30')
  })

  it('marks days outside the named month', () => {
    const grid = monthGrid(2026, 8) // September 2026
    expect(grid[0]?.inMonth).toBe(false) // 30 Aug
    expect(grid.find((day) => day.iso === '2026-09-01')?.inMonth).toBe(true)
  })
})

describe('monthLabel', () => {
  it('names the month and year', () => {
    expect(monthLabel(2026, 8)).toBe('September 2026')
  })
})

describe('shiftMonth', () => {
  it('moves forward, landing on the 1st', () => {
    expect(shiftMonth('2026-09-14', 1)).toBe('2026-10-01')
  })

  it('moves backward across a year boundary', () => {
    expect(shiftMonth('2027-01-04', -1)).toBe('2026-12-01')
  })

  it('does not skip a month when repeated from a day a shorter month lacks', () => {
    // 31 Aug + 1 month naively lands on 1 Oct if the day-of-month (31) is
    // carried across, skipping September, which has no 31st.
    const septemberFirst = shiftMonth('2026-08-31', 1)
    expect(septemberFirst).toBe('2026-09-01')
    expect(shiftMonth(septemberFirst, 1)).toBe('2026-10-01')
  })
})

describe('monthOf', () => {
  it('reads the year and a zero-based month out of the date', () => {
    expect(monthOf('2026-09-14')).toEqual({ year: 2026, month: 8 })
  })
})

describe('monthKey', () => {
  it('is the same for any two days in the same month', () => {
    expect(monthKey('2026-09-01')).toBe(monthKey('2026-09-30'))
  })

  it('differs across a month boundary', () => {
    expect(monthKey('2026-08-31')).not.toBe(monthKey('2026-09-01'))
  })
})

describe('pointRangeLabel', () => {
  it('labels a week as its own start-to-end range', () => {
    // 7 Sep is a Monday; the week it starts runs to Sunday the 13th.
    expect(pointRangeLabel('2026-09-07', 'week')).toBe('7–13 Sep')
  })

  it('names both months when a week crosses one', () => {
    // 31 Aug's week runs into September.
    expect(pointRangeLabel('2026-08-31', 'week')).toBe('31 Aug–6 Sep')
  })

  it('labels a month as its own first-to-last range', () => {
    expect(pointRangeLabel('2026-09-01', 'month')).toBe('Sep 1–30')
  })

  it('uses the right last day for a shorter month', () => {
    expect(pointRangeLabel('2026-02-01', 'month')).toBe('Feb 1–28')
  })

  it('uses the right last day in a leap year', () => {
    expect(pointRangeLabel('2028-02-01', 'month')).toBe('Feb 1–29')
  })
})
