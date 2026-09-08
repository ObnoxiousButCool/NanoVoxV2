import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { GraphPeriodFilter } from './GraphPeriodFilter'
import styles from './GraphPeriodFilter.module.css'

describe('GraphPeriodFilter', () => {
  describe('week mode', () => {
    it('names the 15-day window centred on the given day', () => {
      render(<GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)

      expect(screen.getByText('Sep 7 – Sep 21, 2026')).toBeInTheDocument()
    })

    it('shifts the centre back two weeks on the left chevron', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )

      await user.click(screen.getByRole('button', { name: 'Shift the window back two weeks' }))

      expect(onChange).toHaveBeenCalledWith('2026-08-31')
    })

    it('shifts the centre forward two weeks on the right chevron', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )

      await user.click(screen.getByRole('button', { name: 'Shift the window forward two weeks' }))

      expect(onChange).toHaveBeenCalledWith('2026-09-28')
    })

    it("opens a calendar on the range label naming the centre's month", async () => {
      const user = userEvent.setup()
      render(<GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)

      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('September 2026')).toBeInTheDocument()
    })

    it('marks the centre day solid and the rest of the window pale, leaving the rest plain', async () => {
      const user = userEvent.setup()
      render(<GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)
      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      const day = (label: string) => screen.getByRole('button', { name: label })

      expect(day('September 14, 2026')).toHaveClass(styles.dayCentre ?? '')
      expect(day('September 7, 2026')).toHaveClass(styles.dayInWindow ?? '')
      expect(day('September 21, 2026')).toHaveClass(styles.dayInWindow ?? '')
      expect(day('September 6, 2026')).not.toHaveClass(styles.dayInWindow ?? '')
      expect(day('September 6, 2026')).not.toHaveClass(styles.dayCentre ?? '')
      expect(day('September 22, 2026')).not.toHaveClass(styles.dayInWindow ?? '')
    })

    it('sets the picked day as the new centre and closes the calendar', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )
      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      await user.click(screen.getByRole('button', { name: 'September 21, 2026' }))

      expect(onChange).toHaveBeenCalledWith('2026-09-21')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('browses to another month without moving the centre', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )
      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      await user.click(screen.getByRole('button', { name: 'Next month' }))

      expect(screen.getByText('October 2026')).toBeInTheDocument()
      expect(onChange).not.toHaveBeenCalled()
    })

    it('closes on Escape without changing the centre', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )
      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      await user.keyboard('{Escape}')

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(onChange).not.toHaveBeenCalled()
    })

    it('closes on a click outside the control', async () => {
      const user = userEvent.setup()
      render(
        <div>
          <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />
          <button type="button">elsewhere</button>
        </div>,
      )
      await user.click(screen.getByText('Sep 7 – Sep 21, 2026'))

      await user.click(screen.getByRole('button', { name: 'elsewhere' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('month mode', () => {
    it("names the value's month", () => {
      render(<GraphPeriodFilter mode="month" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)

      expect(screen.getByText('September 2026')).toBeInTheDocument()
    })

    it('shifts to the previous month on the left chevron, landing on its 1st', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="month" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )

      await user.click(screen.getByRole('button', { name: 'Shift to the previous month' }))

      expect(onChange).toHaveBeenCalledWith('2026-08-01')
    })

    it('shifts to the next month on the right chevron', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="month" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )

      await user.click(screen.getByRole('button', { name: 'Shift to the next month' }))

      expect(onChange).toHaveBeenCalledWith('2026-10-01')
    })

    it('marks every day of the selected month, and none outside it', async () => {
      const user = userEvent.setup()
      render(<GraphPeriodFilter mode="month" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)

      await user.click(screen.getByText('September 2026'))

      // No single "centre" day in month mode: the 14th is highlighted the
      // same pale way as every other September day, not singled out solid.
      expect(screen.getByRole('button', { name: 'September 1, 2026' })).toHaveClass(
        styles.dayInWindow ?? '',
      )
      expect(screen.getByRole('button', { name: 'September 30, 2026' })).toHaveClass(
        styles.dayInWindow ?? '',
      )
      expect(screen.getByRole('button', { name: 'September 14, 2026' })).not.toHaveClass(
        styles.dayCentre ?? '',
      )
      expect(screen.getByRole('button', { name: 'August 31, 2026' })).not.toHaveClass(
        styles.dayInWindow ?? '',
      )
      expect(screen.getByRole('button', { name: 'October 1, 2026' })).not.toHaveClass(
        styles.dayInWindow ?? '',
      )
    })

    it('sets the picked day as the new value and closes the calendar', async () => {
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="month" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )
      await user.click(screen.getByText('September 2026'))

      await user.click(screen.getByRole('button', { name: 'August 31, 2026' }))

      expect(onChange).toHaveBeenCalledWith('2026-08-31')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('reports a mode change from its own dropdown', async () => {
    const onModeChange = vi.fn()
    const user = userEvent.setup()
    render(
      <GraphPeriodFilter mode="week" onModeChange={onModeChange} value="2026-09-14" onChange={vi.fn()} />,
    )

    await user.selectOptions(screen.getByLabelText('View by'), 'month')

    expect(onModeChange).toHaveBeenCalledWith('month')
  })
})
