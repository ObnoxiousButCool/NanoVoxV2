import { QueryClient } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { InferencesPage } from '@/features/inferences/InferencesPage'
import { requestUrl } from '@/test/requestUrl'

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
    why: '4 of 12 analyzed calls raise a Process Breakdown finding.',
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

const VOCABULARY = [
  { code: 'unresolved', label: 'Issue unresolved', short_label: 'Unresolved' },
  { code: 'escalated', label: 'Escalated without resolution', short_label: 'Escalated' },
  { code: 'ended_unhappy', label: 'Ended the call unhappy', short_label: 'Unhappy' },
  { code: 'repeat_contact', label: 'Has called more than once', short_label: 'Repeat' },
  { code: 'low_score', label: 'Poorly handled', short_label: 'Low score' },
]

/** One named member and one unnamed: a third of the corpus never states a name. */
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

function json(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: () => Promise.resolve(body),
  } as unknown as Response
}

/**
 * Routed by URL rather than answering everything with one body: the screen now
 * reads two endpoints, and a single-body stub would hand the members matrix an
 * overview payload and fail somewhere that says nothing about why.
 */
function renderInferences(overview: unknown = OVERVIEW, members: unknown = MEMBERS) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        json(requestUrl(input).includes('/dashboard/members-at-risk') ? members : overview),
      ),
    ),
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

  describe('members at risk', () => {
    it('names the warning signs rather than scoring them', async () => {
      // A percentage would be indistinguishable from a measured one while being
      // invented, and would be acted on as though it were fact.
      renderInferences()

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
      renderInferences()

      await screen.findByText(new RegExp('••••9074'))
      const matrix = screen.getByRole('table', { name: 'Members showing warning signs' })
      expect(within(matrix).getByText('Escalated')).toBeInTheDocument()
    })

    it('takes its columns from the response, not from a list in the client', async () => {
      // A factor added to the domain and not to the client would go unread with
      // nothing on screen to say so.
      renderInferences(OVERVIEW, {
        ...MEMBERS,
        factor_vocabulary: [
          ...VOCABULARY,
          { code: 'chased_us', label: 'Chased us for an answer', short_label: 'Chased' },
        ],
      })

      const matrix = await screen.findByRole('table', { name: 'Members showing warning signs' })
      expect(within(matrix).getByText('Chased')).toBeInTheDocument()
    })

    it('states each cell in words as well as in colour', async () => {
      // The cells carry no text. A filled square and a colour are not readable
      // by everyone, and they are the entire content of the row.
      renderInferences()

      const row = await screen.findByRole('row', { name: new RegExp('••••7740') })
      expect(within(row).getByText('Poorly handled')).toBeInTheDocument()
      expect(within(row).getByText('Not issue unresolved')).toBeInTheDocument()
    })

    it('shows the score that separates two members carrying the same signs', async () => {
      // Ranking already used it and the card never drew it, so two rows could
      // sit in a fixed order for a reason nothing on screen gave.
      renderInferences()

      const row = await screen.findByRole('row', { name: new RegExp('••••9074') })
      expect(within(row).getByText('29')).toBeInTheDocument()
    })

    it('says plainly that it is not a prediction', async () => {
      renderInferences()

      await screen.findByText(new RegExp('••••9074'))
      expect(screen.getByText(/not.*a predicted probability/i)).toBeInTheDocument()
    })

    it('links a member to all of their calls, not to one reference', async () => {
      // Searching for the latest reference finds a single call. The row exists
      // because the member has a history; the link has to open that history.
      renderInferences()

      // Masked on the face, whole in the href — the list filters on the real one.
      const link = await screen.findByRole('link', { name: new RegExp('••••9074') })
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('names the member, keeping the identifier beside it', async () => {
      // The name is what a reader recognises; the identifier is what the calls
      // list filters on and what other systems are looked up by. Both, not one.
      renderInferences()

      const link = await screen.findByRole('link', { name: /Maria Gonzalez/ })
      expect(link).toHaveTextContent('Maria Gonzalez (••••9074)')
      expect(link).toHaveAttribute('href', '/calls?member=CHM5519074')
    })

    it('shows the identifier alone when no call stated a name', async () => {
      // A third of the corpus describes the caller instead of naming them.
      // The identifier is still true; "Unknown" would not be.
      renderInferences()

      const link = await screen.findByRole('link', { name: '••••7740' })
      expect(link).toHaveTextContent('••••7740')
      // No brackets: with no name in front of it there is nothing to bracket.
      expect(link.textContent).not.toMatch(/[()]/)
      expect(link).toHaveAttribute('href', '/calls?member=CHM8817740')
    })

    it('reports an empty list as a result, not an omission', async () => {
      renderInferences(OVERVIEW, { basis: 'x', factor_vocabulary: VOCABULARY, members: [] })

      expect(await screen.findByText(/No member is showing a warning sign/)).toBeInTheDocument()
    })
  })
})
