import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { OverviewPage } from '@/features/overview/OverviewPage'

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
  histogram: {
    bins: [
      { label: '0-60', lower: 0, upper: 60, count: 5, is_below_threshold: true },
      { label: '60-100', lower: 60, upper: 100, count: 7, is_below_threshold: false },
    ],
    total: 12,
    below_threshold_count: 5,
    peak: 7,
  },
  categories: [
    {
      code: 'coverage_benefits',
      label: 'Coverage & Benefits',
      count: 4,
      unresolved: 2,
      percentage_of_total: 33.3,
    },
    {
      code: 'broker_attributed',
      label: 'Broker-Attributed',
      count: 0,
      unresolved: 0,
      percentage_of_total: 0,
    },
  ],
  attention: [
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
    },
    {
      rule_id: 'operational_failure_volume',
      title: 'Process Breakdown is affecting 4 calls',
      subject: 'Process Breakdown',
      why: '4 of 12 analysed calls raise a Process Breakdown finding.',
      owner: 'Operations',
      severity: 'HIGH',
      count: 4,
      unresolved: 0,
      references: ['F0008'],
    },
  ],
  taxonomy_coverage: 100,
}

const AGENTS = [
  {
    agent_name: 'Sarah',
    call_count: 5,
    average_score: 80.6,
    min_score: 60,
    max_score: 95,
    resolved: 3,
    partially_resolved: 1,
    escalated: 1,
    unresolved: 0,
    tier: 'AVERAGE',
    note: null,
  },
  {
    agent_name: 'Priya',
    call_count: 1,
    average_score: 96,
    min_score: 96,
    max_score: 96,
    resolved: 1,
    partially_resolved: 0,
    escalated: 0,
    unresolved: 0,
    tier: null,
    note: 'Below n=5 significance threshold',
  },
]

const SIGNALS = {
  categories: [],
  owners: [
    { owner: 'Member Communications', count: 4 },
    { owner: 'Provider Relations', count: 0 },
  ],
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderOverview(overview: unknown = OVERVIEW) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/dashboard/overview')) return Promise.resolve(json(overview))
      if (url.includes('/dashboard/agents')) return Promise.resolve(json(AGENTS))
      if (url.includes('/dashboard/signals')) return Promise.resolve(json(SIGNALS))
      return Promise.resolve(json({}))
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    </AppProviders>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('OverviewPage', () => {
  it('ranks the attention queue with the most severe first', async () => {
    renderOverview()

    const headings = await screen.findAllByRole('heading', { level: 4 })
    expect(headings[0]).toHaveTextContent('Agents are not escalating clinical urgency')
  })

  it('gives every attention item an owner and the calls behind it', async () => {
    renderOverview()

    await screen.findByText('Agents are not escalating clinical urgency')
    expect(screen.getByText('Quality and Clinical')).toBeInTheDocument()
    expect(screen.getByText('C0001 F0006')).toBeInTheDocument()
  })

  it('shows the median and the mean together', async () => {
    // One number alone sits in the gap between the two clusters.
    renderOverview()

    await screen.findByText('65')
    expect(screen.getByText(/Mean/)).toHaveTextContent('64.4')
    expect(screen.getByText(/distribution is split/)).toBeInTheDocument()
  })

  it('prints the industry range beside the resolution rate', async () => {
    // 41.7% means little without the 65–75% it is being judged against.
    renderOverview()

    await screen.findByText('41.7%')
    expect(screen.getByText(/65–75%/)).toBeInTheDocument()
  })

  it('marks how many calls fall below the coaching threshold', async () => {
    renderOverview()

    expect(await screen.findByText(/5 calls fall below the coaching threshold/)).toBeInTheDocument()
  })

  it('draws a category with no calls rather than omitting it', async () => {
    // An absent bar reads as "this does not happen".
    renderOverview()

    await screen.findByText('Coverage & Benefits')
    expect(screen.getByText('Broker-Attributed')).toBeInTheDocument()
  })

  it('shows an unrated agent without a score', async () => {
    // Priya has one call and the best average; the tier is still withheld.
    renderOverview()

    expect(await screen.findByText('Priya · 1')).toBeInTheDocument()
    expect(screen.getByText('Sarah · 5')).toBeInTheDocument()
    expect(screen.getByText('81')).toBeInTheDocument()
  })

  it('ranks rated agents by score, and unrated ones by call count below them', async () => {
    // Sarah is rated (81) so she leads; Priya shows a dash and cannot be ranked
    // against a number, so she falls below regardless of her higher average.
    renderOverview()

    await screen.findByText('Sarah · 5')
    const labels = screen
      .getAllByText(/^(Priya|Sarah) · \d+$/)
      .map((node) => node.textContent)
    expect(labels).toEqual(['Sarah · 5', 'Priya · 1'])
  })

  it('shows an owner carrying no signals as a dash', async () => {
    renderOverview()

    await screen.findByText('Member Communications')
    expect(screen.getByText('Provider Relations')).toBeInTheDocument()
    // Two dashes: the owner with no signals, and Priya's withheld tier.
    expect(screen.getAllByText('—')).toHaveLength(2)
  })

  it('points a fresh install at Analyze instead of showing empty charts', async () => {
    renderOverview({ ...OVERVIEW, metrics: { ...OVERVIEW.metrics, total_calls: 0 } })

    expect(await screen.findByText('No calls analysed yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analyze a call' })).toBeInTheDocument()
  })

  it('says the rules ran when nothing crossed a threshold', async () => {
    // Distinct from "nothing was checked".
    renderOverview({ ...OVERVIEW, attention: [] })

    expect(await screen.findByText(/Nothing has crossed a threshold/)).toBeInTheDocument()
  })

  it('explains a load failure rather than showing a blank screen', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <AppProviders client={client}>
        <MemoryRouter>
          <OverviewPage />
        </MemoryRouter>
      </AppProviders>,
    )

    expect(await screen.findByText(/Could not load the dashboard/)).toBeInTheDocument()
  })
})
