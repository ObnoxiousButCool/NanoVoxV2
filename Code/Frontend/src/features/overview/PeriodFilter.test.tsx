import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PeriodFilter } from './PeriodFilter'

const WEEKS = ['2026-08-31', '2026-09-07', '2026-09-14', '2026-09-21']
// Deliberately not the months of WEEKS. The week starting 31 August holds
// September calls, so the corpus has no August — which is exactly the case
// this component must not offer.
const MONTHS = ['2026-09-01']

function renderFilter(props: Partial<Parameters<typeof PeriodFilter>[0]> = {}) {
  return render(
    <PeriodFilter
      availableWeeks={WEEKS}
      availableMonths={MONTHS}
      anchor={undefined}
      onChange={vi.fn()}
      {...props}
    />,
  )
}

/** Switches the filter into Week mode, which it no longer opens in. */
async function inWeekMode(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.selectOptions(screen.getByLabelText('View by'), 'week')
}

describe('PeriodFilter', () => {
  it('opens in Month, so the default period is one the cards can request', () => {
    // Week mode sends no period until a week is picked, and the card
    // endpoints read that as the whole corpus — so the screen used to open
    // with the top strip on a single week and every other card on every call
    // ever analysed. Month mode resolves to the corpus's latest month, so the
    // default is a real period and the screen agrees with itself on first
    // paint. Asserted here and in OverviewPage, which holds the same default
    // in its own state.
    renderFilter()

    expect(screen.getByLabelText('View by')).toHaveValue('month')
    expect(screen.getByLabelText('Month')).toBeInTheDocument()
    expect(screen.queryByLabelText('Week')).not.toBeInTheDocument()
  })

  it('offers every week, newest first', async () => {
    const user = userEvent.setup()
    renderFilter()
    await inWeekMode(user)

    const options = screen.getAllByRole('option').map((option) => option.textContent)
    expect(options).toContain('Sep 21')
    expect(options.indexOf('Sep 21')).toBeLessThan(options.indexOf('Aug 31'))
  })

  it('reports the picked week as the anchor', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderFilter({ onChange })
    await inWeekMode(user)

    await user.selectOptions(screen.getByLabelText('Week'), '2026-09-07')

    expect(onChange).toHaveBeenCalledWith('2026-09-07')
  })

  it('clears the anchor when the latest week is picked again', async () => {
    // `undefined` means "the latest window" to the API — re-selecting the
    // newest week should say that, not name a date that already means it.
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderFilter({ anchor: '2026-08-31', onChange })
    await inWeekMode(user)

    await user.selectOptions(screen.getByLabelText('Week'), '2026-09-21')

    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('names the month itself, not its last week', async () => {
    // The anchor has to be a date the month owns. Resolving September to the
    // week of the 28th is what made the strip report 11 of the month's 89
    // calls: the period stayed weekly while the label said Month.
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderFilter({ availableMonths: ['2026-08-01', '2026-09-01'], onChange })

    await user.selectOptions(screen.getByLabelText('View by'), 'month')
    expect(screen.getByLabelText('Month')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Month'), '2026-08')

    expect(onChange).toHaveBeenLastCalledWith('2026-08-01')
  })

  it('offers only the months that contain a call', async () => {
    // A week starting 31 August whose calls all fall in September would make
    // August look populated. Picking it would draw an empty strip.
    const user = userEvent.setup()
    renderFilter()

    await user.selectOptions(screen.getByLabelText('View by'), 'month')

    const options = screen.getAllByRole('option').map((option) => option.textContent)
    expect(options).toContain('September 2026')
    expect(options).not.toContain('August 2026')
  })

  it('returns to the latest period when the granularity changes', async () => {
    // The two modes emit different kinds of date — a Monday and a
    // first-of-month — so a carried-over anchor leaves the other dropdown
    // showing a value it has no option for.
    const onChange = vi.fn()
    const user = userEvent.setup()
    renderFilter({ anchor: '2026-09-07', onChange })

    await user.selectOptions(screen.getByLabelText('View by'), 'month')

    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('renders nothing when the corpus has no week to offer', () => {
    const { container } = renderFilter({ availableWeeks: [], availableMonths: [] })

    expect(container).toBeEmptyDOMElement()
  })
})
