import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { GraphPeriodFilter } from './GraphPeriodFilter'

describe('GraphPeriodFilter', () => {
  describe('week mode', () => {
    it('names all three weeks it draws, not just up to the last one', () => {
      render(<GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={vi.fn()} />)

      // The weeks of 7, 14 and 21 September; the third runs to the 27th.
      expect(screen.getByText('Sep 7 – Sep 27, 2026')).toBeInTheDocument()
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

    it('states the period rather than offering it as a control', async () => {
      // It used to open a calendar. The window moves with the chevrons and is
      // seeded by the page header, so a third way to set it was one too many
      // -- and a bordered pill invited a click that would now do nothing.
      const onChange = vi.fn()
      const user = userEvent.setup()
      render(
        <GraphPeriodFilter mode="week" onModeChange={vi.fn()} value="2026-09-14" onChange={onChange} />,
      )

      const period = screen.getByText('Sep 7 – Sep 27, 2026')
      expect(period.tagName).toBe('SPAN')
      await user.click(period)

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(onChange).not.toHaveBeenCalled()
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
