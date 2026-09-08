import { QueryClient } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { OverviewPage } from '@/features/overview/OverviewPage'
import chartStyles from '@/shared/ui/charts.module.css'

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
      why: '4 of 12 analyzed calls raise a Process Breakdown finding.',
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

const VOCABULARY = [
  { code: 'unresolved', label: 'Issue unresolved', short_label: 'Unresolved' },
  { code: 'escalated', label: 'Escalated without resolution', short_label: 'Escalated' },
  { code: 'ended_unhappy', label: 'Ended the call unhappy', short_label: 'Unhappy' },
  { code: 'repeat_contact', label: 'Has called more than once', short_label: 'Repeat' },
  { code: 'low_score', label: 'Poorly handled', short_label: 'Low score' },
]

const MEMBERS = {
  basis: 'Observed warning signs, not a prediction.',
  factor_vocabulary: VOCABULARY,
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
  sentiment: { improved: 0, unchanged: 0, worsened: 0, unclassified: 0, improved_rate: 0 },
  undated_calls: 0,
  available_weeks: ['2026-08-31', '2026-09-07', '2026-09-14'],
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

function renderOverview(
  overview: unknown = OVERVIEW,
  {
    resolution = RESOLUTION,
    members = MEMBERS,
    timeValue = TIME_VALUE,
    pulse = PULSE,
    workMix = WORK_MIX,
  }: {
    resolution?: unknown
    members?: unknown
    timeValue?: unknown
    pulse?: unknown
    workMix?: unknown
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
      if (url.includes('/dashboard/work-mix')) return Promise.resolve(json(workMix))
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
  it('carries each owner count on its own bar', async () => {
    // The prose total is gone; the counts themselves are what the reader has.
    // 4 + 0 owner counts against a 12-call corpus.
    renderOverview()

    const row = await screen.findByText('Member Communications')
    const card = row.closest('section')
    if (!card) throw new Error('owner card has no containing section')
    expect(within(card).getByText('4')).toBeInTheDocument()
    expect(within(card).getByText('—')).toBeInTheDocument()
  })

  it('keeps the double-counting rule reachable, behind the card hint', async () => {
    // Hidden by default but never removed: a reader who wonders why the bars
    // do not sum to the call count has to be able to find out that they cannot.
    renderOverview()

    const heading = await screen.findByText('Signals by owner')
    const card = heading.closest('section')
    if (!card) throw new Error('signals card has no containing section')
    expect(within(card).getByRole('note', { hidden: true })).toHaveTextContent(
      'counted for the team owning the more serious one',
    )
  })

  it('opens a card hint when its icon is pressed', async () => {
    // Hover alone would put every explanation on the dashboard out of reach of
    // a keyboard or a touch screen, so the trigger is a real button.
    renderOverview()

    const heading = await screen.findByText('Signals by owner')
    const card = heading.closest('section')
    if (!card) throw new Error('signals card has no containing section')

    const icon = within(card).getByRole('button', { name: 'How this is counted' })
    expect(icon).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(icon)

    expect(icon).toHaveAttribute('aria-expanded', 'true')
    expect(within(card).getByRole('note')).toBeVisible()
  })

  it('shows the median and the mean together, and says which is which', async () => {
    // One number alone sits in the gap between the two clusters. The card is
    // headed "Average Call Score", so the sub-line has to name the average it
    // shows or the two figures read as a contradiction.
    renderOverview()

    await screen.findByText('65')
    expect(screen.getByText(/Median of every call/)).toHaveTextContent('64.4')
    expect(screen.getByText(/distribution is split/)).toBeInTheDocument()
  })

  it('prints the industry range beside the resolution rate', async () => {
    // 41.7% means little without the 65–75% it is being judged against.
    renderOverview()

    await screen.findByText('41.7%')
    expect(screen.getByText(/65–75%/)).toBeInTheDocument()
  })

  it('keeps the calls below the coaching threshold reachable from their bar', async () => {
    // The sentence counting them is gone, so the bar is the only route to them.
    renderOverview()

    const bar = await screen.findByRole('button', { name: /Show the 5 calls scoring 0/ })
    expect(bar).toBeInTheDocument()
  })

  it('opens a category from the demand chart', async () => {
    renderOverview()

    const link = await screen.findByRole('link', { name: 'Coverage & Benefits' })
    expect(link).toHaveAttribute('href', '/calls?category=coverage_benefits')
  })

  it('leaves a category with no calls unlinked', async () => {
    // Drawn so the absence is visible, but there is nothing behind it to open.
    renderOverview()

    await screen.findByText('Broker Conduct')
    expect(screen.queryByRole('link', { name: 'Broker Conduct' })).not.toBeInTheDocument()
  })

  it('draws a category with no calls rather than omitting it', async () => {
    // An absent bar reads as "this does not happen".
    renderOverview()

    await screen.findByText('Coverage & Benefits')
    expect(screen.getByText('Broker Conduct')).toBeInTheDocument()
  })

  it('shows an unrated agent their average, and withholds only the tier', async () => {
    // Priya has one call and the best average. The arithmetic is sound on one
    // call as on fifty; what one call cannot carry is a GOOD or POOR label.
    renderOverview()

    expect(await screen.findByText('Priya · 1')).toBeInTheDocument()
    expect(screen.getByText('Sarah · 5')).toBeInTheDocument()
    expect(screen.getByText('81')).toBeInTheDocument()

    // Marked, so a thin average does not read as a settled one.
    // The mark is a star for sighted readers; the reason is spelled out for a
    // screen reader, which cannot see one.
    const marked = screen.getByTitle('Below n=5 significance threshold')
    expect(marked).toHaveTextContent('96')
    expect(marked).toHaveTextContent('Below n=5 significance threshold')
  })

  it('keeps rated agents above unrated ones, whatever the averages say', async () => {
    // Priya averages 96 against Sarah's 81 and still sits below her: a tier is
    // a claim about an agent and a one-call average is not, so the two are not
    // ranked against each other even though both now show a number.
    renderOverview()

    await screen.findByText('Sarah · 5')
    const labels = screen
      .getAllByText(/^(Priya|Sarah) · \d+$/)
      .map((node) => node.textContent)
    expect(labels).toEqual(['Sarah · 5', 'Priya · 1'])
  })

  it('shows an owner carrying no signals as a dash', async () => {
    renderOverview()

    const heading = await screen.findByText('Signals by owner')
    const card = heading.closest('section')
    if (!card) throw new Error('signals card has no containing section')

    // One dash in this card: the owner carrying no signals. Scoped to the
    // card itself — "How long an answer takes" has its own dash for its own
    // reason, covered by its own test, and is not what this one is about.
    expect(within(card).getByText('Provider Relations')).toBeInTheDocument()
    expect(within(card).getAllByText('—')).toHaveLength(1)
  })

  it('points a fresh install at Analyze instead of showing empty charts', async () => {
    renderOverview({ ...OVERVIEW, metrics: { ...OVERVIEW.metrics, total_calls: 0 } })

    expect(await screen.findByText('No calls analyzed yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Analyze a call' })).toBeInTheDocument()
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
      // every total below three tall cards and no direction anywhere. The
      // heading that announced this section is gone, so position is the claim:
      // the week has to come before the five-week trend.
      renderOverview()

      const week = await screen.findByText('Calls Monitored')
      const trend = await screen.findByText('Overall Call Quality vs Average Handling Time')

      expect(week.compareDocumentPosition(trend)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    })

    it('says which way each figure moved and by how much', async () => {
      renderOverview()

      expect(await screen.findByText(/54.2 pts on last week/)).toBeInTheDocument()
      expect(screen.getByText(/18.5 pts on last week/)).toBeInTheDocument()
    })

    it('reports the call count as a percentage move against last week', async () => {
      // 7 calls against 8 the week before: a percentage of the count itself,
      // not of some other metric shown beside it.
      renderOverview()

      expect(await screen.findByText(/12.5% on last week/)).toBeInTheDocument()
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

  describe('quality vs handling time', () => {
    it('draws a point on each line for every week that measured it', async () => {
      // The week with no calls (7 Sep) has neither figure, so it contributes
      // no point to either line — two lines, two measured weeks each.
      const { container } = renderOverview()

      await screen.findByText('Overall Call Quality vs Average Handling Time')
      expect(container.getElementsByClassName((chartStyles.point ?? ''))).toHaveLength(4)
    })

    it("shows a week's numbers on hover", async () => {
      const user = userEvent.setup()
      renderOverview()

      const point = await screen.findByRole('img', { name: /31 Aug/ })
      await user.hover(point)

      expect(screen.getByText('Quality 88')).toBeInTheDocument()
      expect(screen.getByText('AHT 8m')).toBeInTheDocument()
    })
  })

  describe('syncing the graph filter from the page filter', () => {
    async function pageHeaderScope(container: HTMLElement): Promise<HTMLElement> {
      await screen.findByText('Operations dashboard')
      const header = container.querySelector('header')
      if (!header) throw new Error('page header not found')
      return header
    }

    async function graphCard(): Promise<HTMLElement> {
      const heading = await screen.findByText('Overall Call Quality vs Average Handling Time')
      const card = heading.closest('section')
      if (!card) throw new Error('quality-vs-handling-time card has no containing section')
      return card
    }

    it("seeds the graph filter's mode and month when the page filter changes to Month", async () => {
      const user = userEvent.setup()
      const { container } = renderOverview()
      const header = await pageHeaderScope(container)
      const card = await graphCard()

      // Defaults to 3-week until the page filter says otherwise.
      expect(within(card).getByLabelText('View by')).toHaveValue('week')

      await user.selectOptions(within(header).getByLabelText('View by'), 'month')
      await user.selectOptions(within(header).getByLabelText('Month'), '2026-08')

      expect(within(card).getByLabelText('View by')).toHaveValue('month')
      expect(await within(card).findByText('August 2026')).toBeInTheDocument()
    })

    it('lets the graph filter move to 3-week mode on its own week, without disturbing the page filter', async () => {
      const user = userEvent.setup()
      const { container } = renderOverview()
      const header = await pageHeaderScope(container)
      const card = await graphCard()

      await user.selectOptions(within(header).getByLabelText('View by'), 'month')
      await user.selectOptions(within(header).getByLabelText('Month'), '2026-08')
      await within(card).findByText('August 2026')

      await user.selectOptions(within(card).getByLabelText('View by'), 'week')
      await user.click(within(card).getByRole('button', { name: 'Shift the window forward two weeks' }))

      expect(within(card).getByLabelText('View by')).toHaveValue('week')
      // The page filter never moved off August.
      expect(within(header).getByLabelText('View by')).toHaveValue('month')
      expect(within(header).getByLabelText('Month')).toHaveValue('2026-08')
    })

    it("lets the graph filter browse to a different month than the page filter's", async () => {
      const user = userEvent.setup()
      const { container } = renderOverview()
      const header = await pageHeaderScope(container)
      const card = await graphCard()

      await user.selectOptions(within(header).getByLabelText('View by'), 'month')
      await user.selectOptions(within(header).getByLabelText('Month'), '2026-08')
      await within(card).findByText('August 2026')

      await user.click(within(card).getByRole('button', { name: 'Shift to the next month' }))

      expect(within(card).getByText('September 2026')).toBeInTheDocument()
      expect(within(header).getByLabelText('Month')).toHaveValue('2026-08')
    })
  })

  describe('who calls', () => {
    it('measures each population against itself, not against the queue', async () => {
      // Stacking by volume would say only that members call most.
      renderOverview()

      expect(await screen.findByText('Member · 28')).toBeInTheDocument()
      expect(screen.getByText('Employer · 15')).toBeInTheDocument()
    })

    it('opens a population’s calls from its bar', async () => {
      // The bar says one of the three fares worse; the calls say which ones.
      renderOverview()

      const link = await screen.findByRole('link', { name: 'Member · 28' })
      expect(link).toHaveAttribute('href', '/calls?caller=MEMBER')
    })

    it('leaves a population with no calls unlinked', async () => {
      // Nothing to open, and a link to an empty list reads as a fault.
      renderOverview(OVERVIEW, {
        workMix: {
          ...WORK_MIX,
          callers: [{ ...WORK_MIX.callers[0], caller_type: 'BROKER', calls: 0 }],
        },
      })

      await screen.findByText('Broker · 0')
      expect(screen.queryByRole('link', { name: /^Broker/ })).not.toBeInTheDocument()
    })
  })

  describe('when the calls come', () => {
    it('offers each hour as a way into the calls that started in it', async () => {
      // The bar says a rota question exists; the calls are what wins the
      // argument for changing one.
      renderOverview()

      expect(
        await screen.findByRole('button', { name: 'Show the 6 calls that started at 13:00' }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('button', { name: 'Show the 11 calls that started at 10:00' }),
      ).toBeInTheDocument()
    })

    it('keeps the staffing reading of the marked hour reachable', async () => {
      // The sentence naming 13:00 was removed, so the marking is now carried by
      // the bar's colour alone and only the hint says what it means.
      renderOverview()

      const heading = await screen.findByText('Hourly call distribution')
      const card = heading.closest('section')
      if (!card) throw new Error('hourly card has no containing section')
      expect(within(card).getByRole('note', { hidden: true })).toHaveTextContent(
        'a staffing question rather than a coaching one',
      )
    })
  })

  describe('the detail behind it', () => {
    it('explains a zero escalation rate instead of leaving it beside a benchmark', async () => {
      // A flat 0% next to "industry range 8-12%" reads as a broken feed. It is
      // not one: the shipped corpus contains no escalated call at all.
      renderOverview({ ...OVERVIEW, metrics: { ...OVERVIEW.metrics, escalation_rate: 0 } })

      expect(await screen.findByText('No analyzed call was escalated')).toBeInTheDocument()
    })

    it('keeps the benchmark when calls do escalate', async () => {
      renderOverview()

      // Two metrics carry a benchmark; the escalation one must be among them.
      expect(await screen.findByText(/8–12%/)).toBeInTheDocument()
      expect(screen.queryByText('No analyzed call was escalated')).not.toBeInTheDocument()
    })
  })

  describe('members at risk', () => {
    it('names the warning signs rather than scoring them', async () => {
      // A percentage would be indistinguishable from a measured one while being
      // invented, and would be acted on as though it were fact.
      renderOverview()

      await screen.findByText(new RegExp('••••9074'))
      // Scoped to the matrix: several of these words also name a metric
      // elsewhere on the page.
      const matrix = screen.getByRole('table', { name: 'Members showing warning signs' })
      expect(within(matrix).getByText('Unresolved')).toBeInTheDocument()
      expect(within(matrix).getByText('Unhappy')).toBeInTheDocument()
      expect(within(matrix).getByText('Repeat')).toBeInTheDocument()
    })

    it('draws a column for a sign nobody is currently showing', async () => {
      // An absent column is indistinguishable from a column of no findings, so
      // the matrix draws every factor the system can observe. No member in the
      // fixture has escalated.
      renderOverview()

      await screen.findByText(new RegExp('••••9074'))
      const matrix = screen.getByRole('table', { name: 'Members showing warning signs' })
      expect(within(matrix).getByText('Escalated')).toBeInTheDocument()
    })

    it('takes its columns from the response, not from a list in the client', async () => {
      // A factor added to the domain and not to the client would go unread with
      // nothing on screen to say so.
      renderOverview(OVERVIEW, {
        members: {
          ...MEMBERS,
          factor_vocabulary: [
            ...VOCABULARY,
            { code: 'chased_us', label: 'Chased us for an answer', short_label: 'Chased' },
          ],
        },
      })

      const matrix = await screen.findByRole('table', { name: 'Members showing warning signs' })
      expect(within(matrix).getByText('Chased')).toBeInTheDocument()
    })

    it('states each cell in words as well as in colour', async () => {
      // The cells carry no text. A filled square and a colour are not readable
      // by everyone, and they are the entire content of the row.
      renderOverview()

      const row = await screen.findByRole('row', { name: new RegExp('••••7740') })
      expect(within(row).getByText('Poorly handled')).toBeInTheDocument()
      expect(within(row).getByText('Not issue unresolved')).toBeInTheDocument()
    })

    it('shows the score that separates two members carrying the same signs', async () => {
      // Ranking already used it and the card never drew it, so two rows could
      // sit in a fixed order for a reason nothing on screen gave.
      renderOverview()

      const row = await screen.findByRole('row', { name: new RegExp('••••9074') })
      expect(within(row).getByText('29')).toBeInTheDocument()
    })

    it('says plainly that it is not a prediction', async () => {
      renderOverview()

      await screen.findByText(new RegExp('••••9074'))
      expect(screen.getByText(/not.*a predicted probability/i)).toBeInTheDocument()
    })

    it('links a member to all of their calls, not to one reference', async () => {
      // Searching for the latest reference finds a single call. The row exists
      // because the member has a history; the link has to open that history.
      renderOverview()

      // Masked on the face, whole in the href — the list filters on the real one.
      const link = await screen.findByRole('link', { name: new RegExp('••••9074') })
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('names the member, keeping the identifier beside it', async () => {
      // The name is what a reader recognises; the identifier is what the calls
      // list filters on and what other systems are looked up by. Both, not one.
      renderOverview()

      const link = await screen.findByRole('link', { name: /Maria Gonzalez/ })
      expect(link).toHaveTextContent('Maria Gonzalez (••••9074)')
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('shows the identifier alone when no call stated a name', async () => {
      // A third of the corpus describes the caller instead of naming them.
      // The identifier is still true; "Unknown" would not be.
      renderOverview()

      const link = await screen.findByRole('link', { name: '••••7740' })
      expect(link).toHaveTextContent('••••7740')
      // No brackets: with no name in front of it there is nothing to bracket.
      expect(link.textContent).not.toMatch(/[()]/)
      expect(link).toHaveAttribute('href', '/calls?member=CHM8817740')
    })

    it('reports an empty list as a result, not an omission', async () => {
      renderOverview(OVERVIEW, { members: { basis: 'x', factor_vocabulary: VOCABULARY, members: [] } })

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

    it('opens only the resolved calls, matching what the card counts', async () => {
      // The card is resolved calls only. A link without the outcome would open
      // the whole category and contradict the figure it was opened from.
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByRole('link', { name: 'Coverage & Benefits' })).toHaveAttribute(
        'href',
        '/calls?category=coverage_benefits&resolution=RESOLVED',
      )
    })

    it('leaves a category that has resolved nothing unlinked', async () => {
      renderOverview()
      const card = await resolutionCard()

      expect(within(card).getByText('Claims & EOB')).toBeInTheDocument()
      expect(
        within(card).queryByRole('link', { name: 'Claims & EOB' }),
      ).not.toBeInTheDocument()
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

    it('opens every call in a category, because every outcome claimed minutes', async () => {
      // Unlike the resolution-time card, this one counts the minutes a
      // category claimed rather than the ones it earned, so the link carries
      // no outcome.
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByRole('link', { name: 'Claims & EOB' })).toHaveAttribute(
        'href',
        '/calls?category=claims_eob',
      )
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
      expect(within(card).getByText('Ran long, still unresolved')).toBeInTheDocument()
      expect(within(card).getByText(/CALLS · 435 MIN · AVG SCORE 79/)).toBeInTheDocument()

      // Which response each one calls for is behind the card's hint. The two
      // boxes are only worth pairing because they need opposite responses, so
      // that has to stay reachable even though it is no longer on the face.
      expect(within(card).getByRole('note', { hidden: true })).toHaveTextContent(
        'coaching the agent would be the wrong response',
      )
    })

    it('says where the dividing line came from', async () => {
      // A reader has to be able to tell a derived threshold from an invented
      // one. Behind the card's hint rather than under the chart: it is a
      // property of the measure, read once, not a finding read every day.
      renderOverview()
      const card = await timeCard()

      expect(within(card).getByRole('note', { hidden: true })).toHaveTextContent(
        'median length of a call that did resolve',
      )
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
