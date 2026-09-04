import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { InferencesPage } from '@/features/inferences/InferencesPage'

/**
 * One item of each rule kind, because the four kinds are exactly what decides
 * where an item's evidence link points. A fixture carrying only one of them
 * would leave three quarters of the mapping unexercised.
 */
const ATTENTION = [
  {
    rule_id: 'clinical_risk_not_escalated',
    title: 'Agents are not escalating clinical urgency',
    subject: 'Unrecognised clinical urgency',
    why: '2 calls where a member described symptoms.',
    owner: 'Quality and Clinical',
    severity: 'CRITICAL',
    count: 2,
    unresolved: 1,
    references: ['C0001', 'F0006'],
    call_filter: { signal: 'clinical_risk' },
  },
  {
    rule_id: 'operational_failure_volume',
    title: 'Process Breakdown is affecting 4 calls',
    subject: 'Process Breakdown',
    why: '4 of 12 analysed calls raise a Process Breakdown finding.',
    owner: 'Operations',
    severity: 'HIGH',
    count: 4,
    unresolved: 2,
    references: ['C0002'],
    call_filter: { l4_category: 'process_breakdown' },
  },
  {
    rule_id: 'unresolved_concentration',
    title: 'Members are not getting resolution on Billing & Premium',
    subject: 'Billing & Premium',
    why: '3 of 5 Billing & Premium calls ended without the problem being solved.',
    owner: 'Operations',
    severity: 'MEDIUM',
    count: 3,
    unresolved: 3,
    references: [],
    call_filter: { category: 'billing_premium', resolution: 'UNRESOLVED' },
  },
]

const OVERVIEW = {
  metrics: {
    total_calls: 12,
    median_score: 65,
    mean_score: 64.4,
    first_contact_resolution_rate: 41.7,
    escalation_rate: 16.7,
    unresolved_rate: 25,
    broker_signal_count: 5,
    distinct_broker_count: 2,
    provisional_score_count: 2,
  },
  histogram: { bins: [], peak: 0, below_threshold_count: 0 },
  categories: [],
  attention: ATTENTION,
  taxonomy_coverage: 100,
}

function json(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => Promise.resolve(body),
  } as unknown as Response
}

function renderInferences(overview: unknown = OVERVIEW) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(json(overview))),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter>
        <InferencesPage />
      </MemoryRouter>
    </AppProviders>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('InferencesPage', () => {
  it('ranks the queue with the most severe first', async () => {
    renderInferences()

    const headings = await screen.findAllByRole('heading', { level: 4 })
    expect(headings[0]).toHaveTextContent('Agents are not escalating clinical urgency')
  })

  it('gives every item an owner and the calls behind it', async () => {
    renderInferences()

    await screen.findByText('Agents are not escalating clinical urgency')
    expect(screen.getByText('Quality and Clinical')).toBeInTheDocument()
    expect(screen.getByText('C0001 F0006')).toBeInTheDocument()
  })

  it('opens the calls an item counted, not every call', async () => {
    renderInferences()

    const link = await screen.findByRole('link', { name: /Open 2 calls in call history/ })
    expect(link).toHaveAttribute('href', '/calls?signal=clinical_risk')
  })

  it('takes the query from the response rather than deriving it from the rule', async () => {
    // The rule kinds are a server-side vocabulary. If this page rebuilt the
    // query itself, a kind added on the server would silently produce a link
    // that returned every call — so the filter is passed through verbatim,
    // whatever it happens to contain.
    renderInferences()

    const link = await screen.findByRole('link', { name: /Open 4 calls in call history/ })
    expect(link).toHaveAttribute('href', '/calls?l4_category=process_breakdown')
  })

  it('carries every parameter of a multi-part filter', async () => {
    // A category link that dropped the outcome would open the whole category
    // and contradict the count it was opened from.
    renderInferences()

    const link = await screen.findByRole('link', { name: /Open 3 calls in call history/ })
    expect(link).toHaveAttribute('href', '/calls?category=billing_premium&resolution=UNRESOLVED')
  })

  it('says "1 call" rather than "1 calls"', async () => {
    renderInferences({
      ...OVERVIEW,
      attention: [{ ...ATTENTION[0], count: 1 }],
    })

    expect(
      await screen.findByRole('link', { name: /Open 1 call in call history/ }),
    ).toBeInTheDocument()
  })

  it('leaves an item with no filter unlinked rather than linking to everything', async () => {
    renderInferences({
      ...OVERVIEW,
      attention: [{ ...ATTENTION[0], call_filter: {} }],
    })

    await screen.findByText('Agents are not escalating clinical urgency')
    expect(screen.queryByRole('link', { name: /call history/ })).not.toBeInTheDocument()
  })

  it('says the rules ran when nothing crossed a threshold', async () => {
    // Distinct from "nothing was checked".
    renderInferences({ ...OVERVIEW, attention: [] })

    expect(await screen.findByText(/Nothing has crossed a threshold/)).toBeInTheDocument()
  })
})
