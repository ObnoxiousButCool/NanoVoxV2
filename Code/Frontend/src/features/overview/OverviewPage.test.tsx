import { QueryClient } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
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


const RESOLUTION = {
  resolved_calls: 6,
  total_calls: 12,
  median_minutes: 12,
  longest_minutes: 25,
  bands: [
    { label: '0-10', lower: 0, upper: 10, count: 2 },
    { label: '10-20', lower: 10, upper: 20, count: 3 },
    { label: '20+', lower: 20, upper: null, count: 1 },
  ],
  categories: [
    {
      code: 'coverage_benefits',
      label: 'Coverage & Benefits',
      resolved_calls: 4,
      median_minutes: 18,
      longest_minutes: 25,
    },
    {
      code: 'pharmacy',
      label: 'Pharmacy',
      resolved_calls: 2,
      median_minutes: 8,
      longest_minutes: 9,
    },
    // Configured but has resolved nothing: shown, so the absence is visible.
    {
      code: 'claims_eob',
      label: 'Claims & EOB',
      resolved_calls: 0,
      median_minutes: 0,
      longest_minutes: 0,
    },
  ],
}

const TIME_VALUE = {
  total_minutes: 600,
  resolved_minutes: 150,
  unproductive_minutes: 450,
  productive_share: 25,
  resolved_median_minutes: 10,
  fast_fail: { calls: 3, minutes: 15, average_score: 48 },
  slow_fail: { calls: 9, minutes: 435, average_score: 79 },
  categories: [
    {
      code: 'claims_eob',
      label: 'Claims & EOB',
      total_minutes: 400,
      resolved_minutes: 50,
      unproductive_minutes: 350,
      unproductive_share: 87.5,
      by_outcome: [
        { resolution: 'RESOLVED', minutes: 50 },
        { resolution: 'PARTIALLY RESOLVED', minutes: 300 },
        { resolution: 'ESCALATED', minutes: 40 },
        { resolution: 'UNRESOLVED', minutes: 10 },
      ],
    },
    {
      code: 'pharmacy',
      label: 'Pharmacy',
      total_minutes: 200,
      resolved_minutes: 100,
      unproductive_minutes: 100,
      unproductive_share: 50,
      by_outcome: [
        { resolution: 'RESOLVED', minutes: 100 },
        { resolution: 'PARTIALLY RESOLVED', minutes: 100 },
        { resolution: 'ESCALATED', minutes: 0 },
        { resolution: 'UNRESOLVED', minutes: 0 },
      ],
    },
  ],
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

/** A falling series, which is what the trend card exists to make visible. */
const PULSE = {
  points: [
    {
      starting: '2026-08-31',
      label: '31 Aug',
      calls: 8,
      median_score: 88,
      resolution_rate: 87.5,
      median_handle_minutes: 8,
    },
    {
      starting: '2026-09-07',
      label: '7 Sep',
      calls: 0,
      median_score: null,
      resolution_rate: null,
      median_handle_minutes: null,
    },
    {
      starting: '2026-09-14',
      label: '14 Sep',
      calls: 7,
      median_score: 69.5,
      resolution_rate: 33.3,
      median_handle_minutes: 6.5,
    },
  ],
  latest: {
    starting: '2026-09-14',
    label: '14 Sep',
    calls: 7,
    median_score: 69.5,
    resolution_rate: 33.3,
    median_handle_minutes: 6.5,
  },
  previous: {
    starting: '2026-08-31',
    label: '31 Aug',
    calls: 8,
    median_score: 88,
    resolution_rate: 87.5,
    median_handle_minutes: 8,
  },
  delta: {
    calls: -1,
    median_score: -18.5,
    resolution_rate: -54.2,
    median_handle_minutes: -1.5,
  },
  sentiment: { improved: 44, unchanged: 5, worsened: 1, unclassified: 0, improved_rate: 88 },
  undated_calls: 0,
}

const WORK_MIX = {
  callers: [
    {
      caller_type: 'MEMBER',
      calls: 28,
      share: 56,
      resolution_rate: 57.1,
      average_score: 77,
      average_handle_minutes: 7.1,
    },
    {
      caller_type: 'EMPLOYER',
      calls: 15,
      share: 30,
      resolution_rate: 40,
      average_score: 76.1,
      average_handle_minutes: 7.6,
    },
  ],
  caller_total: 43,
  unattributed_calls: 0,
  hours: [
    {
      hour: 10,
      label: '10:00',
      calls: 11,
      average_score: 73.8,
      resolution_rate: 54.5,
      is_thin: false,
    },
    { hour: 13, label: '13:00', calls: 6, average_score: 63.2, resolution_rate: 33, is_thin: false },
  ],
  busiest_hour: '10:00',
  weakest_hour: '13:00',
}

const SPEED = {
  agents: [
    {
      agent_name: 'Sarah',
      calls: 5,
      average_score: 84.2,
      average_handle_minutes: 10,
      is_comparable: true,
    },
    {
      agent_name: 'Brad',
      calls: 4,
      average_score: 57,
      average_handle_minutes: 4.7,
      is_comparable: false,
    },
  ],
  faster: { label: 'under 6.7 min', calls: 25, average_score: 67.6, average_handle_minutes: 5.6 },
  slower: {
    label: 'at 6.7 min and over',
    calls: 25,
    average_score: 84.2,
    average_handle_minutes: 9,
  },
  split_minutes: 6.7,
  score_gap: 16.6,
  flagged_agents: 1,
}

function renderOverview(
  overview: unknown = OVERVIEW,
  {
    resolution = RESOLUTION,
    members = MEMBERS,
    timeValue = TIME_VALUE,
    pulse = PULSE,
  }: {
    resolution?: unknown
    members?: unknown
    timeValue?: unknown
    pulse?: unknown
  } = {},
) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/dashboard/overview')) return Promise.resolve(json(overview))
      if (url.includes('/dashboard/agents')) return Promise.resolve(json(AGENTS))
      if (url.includes('/dashboard/signals')) return Promise.resolve(json(SIGNALS))
      if (url.includes('/dashboard/resolution-time')) return Promise.resolve(json(resolution))
      if (url.includes('/dashboard/time-value')) return Promise.resolve(json(timeValue))
      if (url.includes('/dashboard/members-at-risk')) return Promise.resolve(json(members))
      if (url.includes('/dashboard/pulse')) return Promise.resolve(json(pulse))
      if (url.includes('/dashboard/work-mix')) return Promise.resolve(json(WORK_MIX))
      if (url.includes('/dashboard/handle-time-quality')) return Promise.resolve(json(SPEED))
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

/**
 * The resolution-time card, scoped.
 *
 * Several of its figures — a bare "12", a category label, a dash — also appear
 * elsewhere on this page, so an unscoped query can match another card's content
 * and pass while this one is still loading.
 */
async function resolutionCard(): Promise<HTMLElement> {
  const heading = await screen.findByText('How long an answer takes')
  const card = heading.closest('section')
  if (!card) throw new Error('resolution card has no containing section')
  await within(card).findByText('MEDIAN MINUTES TO RESOLVE')
  return card
}

async function timeCard(): Promise<HTMLElement> {
  const heading = await screen.findByText('Productive and unproductive minutes')
  const card = heading.closest('section')
  if (!card) throw new Error('time card has no containing section')
  await within(card).findByText('TOTAL TIME ON CALLS')
  return card
}

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

  describe('where we stand', () => {
    it('leads with the week, not with the all-time total', async () => {
      // The screen used to open on a scrolling list of member identifiers, with
      // every total below three tall cards and no direction anywhere.
      renderOverview()

      expect(await screen.findByText('Where we stand — most recent week')).toBeInTheDocument()
      expect(await screen.findByText('Calls this week')).toBeInTheDocument()
    })

    it('says which way each figure moved and by how much', async () => {
      renderOverview()

      expect(await screen.findByText(/54.2 pts on last week/)).toBeInTheDocument()
      expect(screen.getByText(/18.5 pts on last week/)).toBeInTheDocument()
    })

    it('marks a fall as bad and a rise as good, per measure', async () => {
      // Handle time is the exception: shorter is an answer found faster or a
      // member brushed off, and this figure cannot tell them apart.
      renderOverview()

      const resolution = await screen.findByText(/54.2 pts on last week/)
      const handleTime = screen.getByText(/1.5 min on last week/)

      expect(resolution.className).not.toEqual(handleTime.className)
    })

    it('says so rather than inventing a comparison when there is no prior week', async () => {
      renderOverview(OVERVIEW, { pulse: { ...PULSE, previous: null, delta: null } })

      expect((await screen.findAllByText('No previous week')).length).toBeGreaterThan(0)
    })
  })

  describe('the weekly trend', () => {
    it('gives every week as a value, not only as a line', async () => {
      // The plot is SVG with no text in it. The table is the same data in the
      // form a screen reader and a printed page can use.
      renderOverview()

      const table = await screen.findByRole('table', { name: /weekly series/i })
      expect(within(table).getByText('87.5%')).toBeInTheDocument()
      expect(within(table).getByText('33.3%')).toBeInTheDocument()
    })

    it('shows a week with no calls as a gap rather than a zero', async () => {
      // A zero would read as "nobody was helped that week" instead of "nobody
      // called that week".
      renderOverview()

      const table = await screen.findByRole('table', { name: /weekly series/i })
      const week = within(table).getByRole('row', { name: /7 Sep/ })
      expect(within(week).getAllByText('—')).toHaveLength(2)
    })
  })

  describe('what speed costs', () => {
    it('states the gap between the two halves of the calls', async () => {
      renderOverview()

      expect(await screen.findByText(/gap of/)).toBeInTheDocument()
      expect(screen.getByText('16.6')).toBeInTheDocument()
    })

    it('says the split is over calls, not over agents', async () => {
      // The distinction the statistic depends on: thirteen agents is thirteen
      // points and most of them have four calls.
      renderOverview()

      expect(
        await screen.findByText(/measured over calls rather than over agents/),
      ).toBeInTheDocument()
    })

    it('refuses to call the relationship a cause', async () => {
      renderOverview()

      expect(
        await screen.findByText(/not which one causes the other/),
      ).toBeInTheDocument()
    })

    it('plots an agent below the threshold and marks them', async () => {
      renderOverview()

      const table = await screen.findByRole('table', { name: /Average score and Average minutes/i })
      expect(within(table).getByRole('row', { name: /Brad/ })).toBeInTheDocument()
      expect(screen.getByText(/below the tier threshold/)).toBeInTheDocument()
    })
  })

  describe('who calls', () => {
    it('measures each population against itself, not against the queue', async () => {
      // Stacking by volume would say only that members call most.
      renderOverview()

      expect(await screen.findByText('Member · 28')).toBeInTheDocument()
      expect(screen.getByText('Employer · 15')).toBeInTheDocument()
    })
  })

  describe('when the calls come', () => {
    it('names the weakest staffed hour as a staffing question', async () => {
      renderOverview()

      expect(await screen.findByText(/staffing question rather than a coaching one/)).toBeInTheDocument()
      expect(screen.getByText('13:00')).toBeInTheDocument()
    })
  })

  describe('the detail behind it', () => {
    it('explains a zero escalation rate instead of leaving it beside a benchmark', async () => {
      // A flat 0% next to "industry range 8-12%" reads as a broken feed. It is
      // not one: the shipped corpus contains no escalated call at all.
      renderOverview({ ...OVERVIEW, metrics: { ...OVERVIEW.metrics, escalation_rate: 0 } })

      expect(await screen.findByText('No analysed call was escalated')).toBeInTheDocument()
    })

    it('keeps the benchmark when calls do escalate', async () => {
      renderOverview()

      // Two metrics carry a benchmark; the escalation one must be among them.
      expect(await screen.findByText(/8–12%/)).toBeInTheDocument()
      expect(screen.queryByText('No analysed call was escalated')).not.toBeInTheDocument()
    })
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

  describe('resolution time', () => {
    it('reports the time to resolve, not the time on the phone', async () => {
      // Handle time over every call rewards ending the call rather than solving
      // the problem, so the headline is measured over resolved calls only.
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByText('12')).toBeInTheDocument()
      expect(within(card).getByText('OF 12 CALLS RESOLVED')).toBeInTheDocument()
    })

    it('draws the duration bands', async () => {
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByText('0-10 MIN')).toBeInTheDocument()
      expect(within(card).getByText('10-20 MIN')).toBeInTheDocument()
      expect(within(card).getByText('20+ MIN')).toBeInTheDocument()
    })

    it('breaks the time down by category, slowest first', async () => {
      // A single median across a pharmacy query and a coverage appeal describes
      // neither, and moves when the call mix changes rather than the handling.
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByText('18 min')).toBeInTheDocument()
      expect(within(card).getByText('8 min')).toBeInTheDocument()
    })

    it('shows a category that has resolved nothing as a dash, not a zero', async () => {
      // No time was measured, which is not the same as a fast one.
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByText('Claims & EOB')).toBeInTheDocument()
      expect(within(card).getByText('—')).toBeInTheDocument()
    })

    it('says so plainly when nothing has been resolved at all', async () => {
      renderOverview(OVERVIEW, {
        resolution: { ...RESOLUTION, resolved_calls: 0, bands: [], categories: [] },
      })

      expect(
        await screen.findByText(/No call in this corpus reached a resolution/),
      ).toBeInTheDocument()
    })
  })

  describe('what the time bought', () => {
    it('reports the share of minutes, not the share of calls', async () => {
      // Half the calls resolving is not the same as half the time being well
      // spent, and the minutes are the number a manager answers for.
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByText('10.0h')).toBeInTheDocument()
      expect(within(card).getByText('25%')).toBeInTheDocument()
      expect(within(card).getByText('BOUGHT A RESOLUTION')).toBeInTheDocument()
      expect(within(card).getByText('7.5h')).toBeInTheDocument()
    })

    it('lays the categories out by the time they claim', async () => {
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByText('400 min')).toBeInTheDocument()
      const labels = within(card)
        .getAllByTitle(/bought no resolution/)
        .map((element) => element.textContent)
      expect(labels).toEqual(['Claims & EOB', 'Pharmacy'])
    })

    it('separates the two failure modes, which need opposite responses', async () => {
      // Reported as one "12 unresolved calls", the nine agents who did the work
      // against a system with no answer get coached for the other three's
      // problem.
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByText('Ended early, unresolved')).toBeInTheDocument()
      expect(within(card).getByText(/brushed off/)).toBeInTheDocument()
      expect(within(card).getByText('Ran long, still unresolved')).toBeInTheDocument()
      expect(within(card).getByText(/no answer existed/)).toBeInTheDocument()
      expect(within(card).getByText(/CALLS · 435 MIN · AVG SCORE 79/)).toBeInTheDocument()
    })

    it('says where the dividing line came from', async () => {
      // A reader has to be able to tell a derived threshold from an invented one.
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByText(/median length of a call that did resolve/)).toBeInTheDocument()
      expect(within(card).getByText('10 minutes')).toBeInTheDocument()
    })

    it('says so plainly when no call has a duration', async () => {
      renderOverview(OVERVIEW, {
        timeValue: { ...TIME_VALUE, total_minutes: 0, categories: [] },
      })

      expect(
        await screen.findByText(/no minutes to account for/),
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
