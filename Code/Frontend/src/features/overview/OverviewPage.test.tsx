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
      label: 'Broker Conduct',
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

const EFFORT = {
  calls_with_duration: 12,
  median_minutes: 10,
  mean_minutes: 10.8,
  longest_minutes: 20,
  long_call_count: 4,
  long_call_threshold: 20,
  identified_members: 10,
  repeat_members: 2,
  calls_by_repeat_members: 5,
  repeat_contact_rate: 20,
  median_minutes_to_answer: 25,
  members_with_answer: 6,
  members_without_answer: 4,
}

const MEMBERS = {
  basis: 'Observed warning signs, not a prediction.',
  members: [
    {
      member_id: 'CHM5519074',
      member_name: 'Maria Gonzalez',
      call_count: 3,
      factors: ['unresolved', 'ended_unhappy', 'repeat_contact'],
      factor_labels: ['Issue unresolved', 'Ended the call unhappy', 'Has called more than once'],
      lowest_score: 29,
      latest_reference: 'F0006',
      references: ['F0006', 'C0001'],
    },
    {
      member_id: 'CHM8817740',
      member_name: null,
      call_count: 1,
      factors: ['low_score'],
      factor_labels: ['Poorly handled'],
      lowest_score: 46,
      latest_reference: 'C0002',
      references: ['C0002'],
    },
  ],
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderOverview(
  overview: unknown = OVERVIEW,
  { effort = EFFORT, members = MEMBERS }: { effort?: unknown; members?: unknown } = {},
) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/dashboard/overview')) return Promise.resolve(json(overview))
      if (url.includes('/dashboard/agents')) return Promise.resolve(json(AGENTS))
      if (url.includes('/dashboard/signals')) return Promise.resolve(json(SIGNALS))
      if (url.includes('/dashboard/effort')) return Promise.resolve(json(effort))
      if (url.includes('/dashboard/members-at-risk')) return Promise.resolve(json(members))
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

  it('says how many calls the owner bars account for', async () => {
    // The bars total flagged calls, not findings, so the card states the figure
    // rather than leaving the reader to wonder why it is under the call count.
    // 4 + 0 owner counts against a 12-call corpus.
    renderOverview()

    const note = await screen.findByText(/raise at least one signal/)
    expect(note).toHaveTextContent('4 of 12 calls raise at least one signal')
    expect(note).toHaveTextContent('counted for the team owning the more serious one')
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
    expect(screen.getByText('Broker Conduct')).toBeInTheDocument()
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

  describe('members at risk', () => {
    it('names the warning signs rather than scoring them', async () => {
      // A percentage would be indistinguishable from a measured one while being
      // invented, and would be acted on as though it were fact.
      renderOverview()

      expect(await screen.findByText(/CHM5519074/)).toBeInTheDocument()
      expect(screen.getByText('Issue unresolved')).toBeInTheDocument()
      expect(screen.getByText('Ended the call unhappy')).toBeInTheDocument()
      expect(screen.getByText('Has called more than once')).toBeInTheDocument()
    })

    it('says plainly that it is not a prediction', async () => {
      renderOverview()

      await screen.findByText(/CHM5519074/)
      expect(screen.getByText(/not.*a predicted probability/i)).toBeInTheDocument()
    })

    it('links a member to all of their calls, not to one reference', async () => {
      // Searching for the latest reference finds a single call. The row exists
      // because the member has a history; the link has to open that history.
      renderOverview()

      const link = await screen.findByRole('link', { name: /CHM5519074/ })
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('names the member, keeping the identifier beside it', async () => {
      // The name is what a reader recognises; the identifier is what the calls
      // list filters on and what other systems are looked up by. Both, not one.
      renderOverview()

      const link = await screen.findByRole('link', { name: /Maria Gonzalez/ })
      expect(link).toHaveTextContent('Maria Gonzalez (CHM5519074)')
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('shows the identifier alone when no call stated a name', async () => {
      // A third of the corpus describes the caller instead of naming them.
      // The identifier is still true; "Unknown" would not be.
      renderOverview()

      const link = await screen.findByRole('link', { name: 'CHM8817740' })
      expect(link).toHaveTextContent('CHM8817740')
      expect(link.textContent).not.toMatch(/[()]/)
    })

    it('reports an empty list as a result, not an omission', async () => {
      renderOverview(OVERVIEW, { members: { basis: 'x', members: [] } })

      expect(await screen.findByText(/No member is showing a warning sign/)).toBeInTheDocument()
    })
  })

  describe('effort', () => {
    it('shows what an answer costs a member', async () => {
      renderOverview()

      expect(await screen.findByText('20%')).toBeInTheDocument()
      expect(screen.getByText('CALLED MORE THAN ONCE')).toBeInTheDocument()
      expect(screen.getByText(/called back/)).toBeInTheDocument()
    })

    it('measures time to an answer per member, over those who got one', async () => {
      renderOverview()

      // 25 minutes across the 6 members who reached a resolution — not the
      // 10-minute median call, which is a different question.
      expect(await screen.findByText('25')).toBeInTheDocument()
      expect(screen.getByText('MEDIAN MINUTES TO AN ANSWER')).toBeInTheDocument()
      expect(screen.getByText(/Measured over the/)).toHaveTextContent(
        '6 of 10 identified members who reached a resolution',
      )
    })

    it('counts members still waiting rather than averaging them in as zero', async () => {
      // Their clock has not stopped. Folding them in would make the reported
      // time to an answer fall the longer they are left waiting.
      renderOverview()

      expect(await screen.findByText('STILL WITHOUT ONE')).toBeInTheDocument()
      expect(screen.getByText(/still without an answer are left out/)).toBeInTheDocument()
    })

    it('explains a zero repeat rate rather than implying nobody struggles', async () => {
      // On a corpus where every member called once, zero is a property of the
      // sample, not evidence that effort is low.
      renderOverview(OVERVIEW, {
        effort: { ...EFFORT, repeat_members: 0, calls_by_repeat_members: 0, repeat_contact_rate: 0 },
      })

      expect(
        await screen.findByText(/the measure is in place, the calls to find are not/i),
      ).toBeInTheDocument()
    })
  })

  describe('the score distribution', () => {
    it('offers each populated bar as a way into those calls', async () => {
      renderOverview()

      await screen.findByText('Coverage & Benefits')
      expect(
        screen.getByRole('button', { name: 'Show the 5 calls scoring 0 to 59' }),
      ).toBeInTheDocument()
    })

    it('runs the last bin to 100 rather than 99', async () => {
      // Bins are half-open except the last, which has to hold a perfect score.
      // Off by one here and no call scoring 100 would ever be reachable.
      renderOverview()

      await screen.findByText('Coverage & Benefits')
      expect(
        screen.getByRole('button', { name: 'Show the 7 calls scoring 60 to 100' }),
      ).toBeInTheDocument()
    })

    it('says "1 call" rather than "1 calls"', async () => {
      renderOverview({
        ...OVERVIEW,
        histogram: {
          ...OVERVIEW.histogram,
          bins: [
            { label: '0-60', lower: 0, upper: 60, count: 1, is_below_threshold: true },
            { label: '60-100', lower: 60, upper: 100, count: 7, is_below_threshold: false },
          ],
        },
      })

      await screen.findByText('Coverage & Benefits')
      expect(
        screen.getByRole('button', { name: 'Show the 1 call scoring 0 to 59' }),
      ).toBeInTheDocument()
    })

    it('leaves an empty bar inert', async () => {
      // Nothing to show, so nothing to press.
      renderOverview({
        ...OVERVIEW,
        histogram: {
          ...OVERVIEW.histogram,
          bins: [
            { label: '0-60', lower: 0, upper: 60, count: 0, is_below_threshold: true },
            { label: '60-100', lower: 60, upper: 100, count: 7, is_below_threshold: false },
          ],
        },
      })

      await screen.findByText('Coverage & Benefits')
      expect(screen.queryByRole('button', { name: /scoring 0 to 59/ })).not.toBeInTheDocument()
    })
  })
})
