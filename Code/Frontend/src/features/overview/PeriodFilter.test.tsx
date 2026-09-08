import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PeriodFilter } from './PeriodFilter'

const WEEKS = ['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21']

describe('PeriodFilter', () => {
  it('offers every week, newest first', () => {
    render(<PeriodFilter availableWeeks={WEEKS} anchor={undefined} onChange={vi.fn()} />)

    const options = screen.getAllByRole('option').map((option) => option.textContent)
    expect(options).toContain('Sep 21')
    expect(options.indexOf('Sep 21')).toBeLessThan(options.indexOf('Aug 31'))
  })

  it('reports the picked week as the anchor', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<PeriodFilter availableWeeks={WEEKS} anchor={undefined} onChange={onChange} />)

    await user.selectOptions(screen.getByLabelText('Week'), '2026-09-07')

    expect(onChange).toHaveBeenCalledWith('2026-09-07')
  })

  it('clears the anchor when the latest week is picked again', async () => {
    // `undefined` means "the latest window" to the API — re-selecting the
    // newest week should say that, not name a date that already means it.
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<PeriodFilter availableWeeks={WEEKS} anchor="2026-08-31" onChange={onChange} />)

    await user.selectOptions(screen.getByLabelText('Week'), '2026-09-21')

    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('switches to naming months, and resolves a month to its last week', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<PeriodFilter availableWeeks={WEEKS} anchor={undefined} onChange={onChange} />)

    await user.selectOptions(screen.getByLabelText('View by'), 'month')
    expect(screen.getByLabelText('Month')).toBeInTheDocument()
    expect(screen.getByText('August 2026')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Month'), '2026-08')

    // August only contains one of these weeks: the 31st.
    expect(onChange).toHaveBeenCalledWith('2026-08-31')
  })

  it('renders nothing when the corpus has no week to offer', () => {
    const { container } = render(
      <PeriodFilter availableWeeks={[]} anchor={undefined} onChange={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
