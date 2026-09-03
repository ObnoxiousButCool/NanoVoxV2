import { QueryClient } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { CallsPage } from '@/features/calls/CallsPage'

function call(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    reference: 'F0006',
    title: 'Fixture call F0006',
    summary: 'A coverage_benefits call that ended UNRESOLVED.',
    category: 'claims_eob',
    agent_name: 'Brad',
    member_id: 'CHM6672290',
    member_name: 'Terrence Boyd',
    resolution: 'UNRESOLVED',
    score: 30,
    tier: 'POOR',
    score_status: 'final',
    signal_codes: ['clinical_risk'],
    broker_names: [],
    analysed_at: '2026-08-28T10:00:00Z',
    ...overrides,
  }
}

function page(items: unknown[], extra: Record<string, unknown> = {}) {
  return {
    items,
    total: items.length,
    limit: 25,
    offset: 0,
    has_more: false,
    ...extra,
  }
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** What the filter dropdowns are populated from. */
const TAXONOMY = {
  categories: [
    { code: 'billing', label: 'Billing', description: null },
    { code: 'claims_eob', label: 'Claims & EOB', description: null },
  ],
  l4_categories: [],
  signal_types: [{ code: 'clinical_risk', label: 'Clinical Risk', severity: 'CRITICAL' }],
  sentiment_states: [],
  resolutions: ['RESOLVED', 'UNRESOLVED'],
  severities: [],
  tiers: { good: 85, average: 70, min_calls_for_tier_rating: 5 },
  rubric_version: '1.0.0',
}
const AGENT_OPTIONS = [{ agent_name: 'Sarah', call_count: 5 }]
const BROKER_OPTIONS = [{ broker_name: 'Marcus Trent', signals: 4 }]

/** Records every requested URL so filters can be asserted on the query itself. */
function stubCalls(body: unknown) {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      urls.push(url)
      // The dropdowns are populated from live data, so the page fetches these
      // alongside the calls themselves.
      if (url.includes('/taxonomy')) return Promise.resolve(json(TAXONOMY))
      if (url.includes('/dashboard/agents')) return Promise.resolve(json(AGENT_OPTIONS))
      if (url.includes('/dashboard/brokers')) return Promise.resolve(json(BROKER_OPTIONS))
      return Promise.resolve(json(body))
    }),
  )
  return urls
}

/** Renders at `entry`, so the URL-driven filters are exercisable. */
function renderCalls(entry = '/calls') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <CallsPage />
      </MemoryRouter>
    </AppProviders>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CallsPage', () => {
  it('lists a call with the evidence a reviewer needs to triage it', async () => {
    stubCalls(page([call()]))
    renderCalls()

    expect(await screen.findByText('F0006')).toBeInTheDocument()
    // Scoped to the table: 'UNRESOLVED' is also an option in the Outcome filter.
    const rows = within(screen.getAllByRole('rowgroup')[1] as HTMLElement)
    expect(rows.getByText('Brad')).toBeInTheDocument()
    expect(rows.getByText('UNRESOLVED')).toBeInTheDocument()
    expect(rows.getByText('30')).toBeInTheDocument()
    expect(rows.getByText('clinical risk')).toBeInTheDocument()
  })

  it('marks a withheld score rather than printing it as fact', async () => {
    stubCalls(page([call({ score_status: 'provisional' })]))
    renderCalls()

    expect(await screen.findByText('WITHHELD')).toBeInTheDocument()
  })

  it('links each row to the call it came from', async () => {
    stubCalls(page([call({ id: 7 })]))
    renderCalls()

    const link = await screen.findByRole('link', { name: 'F0006' })
    expect(link).toHaveAttribute('href', '/calls/7')
  })

  it('narrows the server query when a filter is pressed', async () => {
    // Filtering client-side would make the count under the table a lie.
    const urls = stubCalls(page([call()]))
    renderCalls()
    await screen.findByText('F0006')

    await userEvent.click(screen.getByRole('button', { name: 'Unresolved only' }))

    await waitFor(() => {
      expect(urls.some((url) => url.includes('resolution=UNRESOLVED'))).toBe(true)
    })
  })

  it('combines two filters into one query instead of replacing', async () => {
    const urls = stubCalls(page([call()]))
    renderCalls()
    await screen.findByText('F0006')

    await userEvent.click(screen.getByRole('button', { name: 'Unresolved only' }))
    await userEvent.click(screen.getByRole('button', { name: 'Broker signal' }))

    await waitFor(() => {
      expect(
        urls.some((url) => url.includes('resolution=UNRESOLVED') && url.includes('has_broker_signal=true')),
      ).toBe(true)
    })
  })

  it('releases a filter when it is pressed a second time', async () => {
    stubCalls(page([call()]))
    renderCalls()
    await screen.findByText('F0006')

    const button = screen.getByRole('button', { name: 'Clinical risk' })
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-pressed', 'false')
  })

  it('returns to the first page when the filter changes', async () => {
    // Page 3 of the old result set is not page 3 of the new one.
    const urls = stubCalls(page([call()], { has_more: true, total: 60 }))
    renderCalls()
    await screen.findByText('F0006')

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => {
      expect(urls.some((url) => url.includes('offset=25'))).toBe(true)
    })

    await userEvent.click(screen.getByRole('button', { name: 'Score under 65' }))

    await waitFor(() => {
      const last = urls[urls.length - 1] ?? ''
      expect(last).toContain('max_score=64')
      expect(last).toContain('offset=0')
    })
  })

  it('counts matching calls, not the calls on this page', async () => {
    stubCalls(page([call()], { total: 60, has_more: true }))
    renderCalls()

    expect(await screen.findByText(/Showing 1–1 of 60/)).toBeInTheDocument()
  })

  it('cannot page back from the first page', async () => {
    stubCalls(page([call()]))
    renderCalls()

    await screen.findByText('F0006')
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('tells a user with filters on how to widen an empty result', async () => {
    stubCalls(page([]))
    renderCalls()

    await screen.findByText('No calls match')
    expect(screen.getByText('Nothing has been analysed yet.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Unresolved only' }))
    expect(await screen.findByText('Clear a filter to widen the search.')).toBeInTheDocument()
  })

  it('shows a dash where no agent was identified', async () => {
    stubCalls(page([call({ agent_name: null })]))
    renderCalls()

    await screen.findByText('F0006')
    // Scoped to the agent cell: the member cell shows a dash of its own when a
    // call never states an identifier.
    const row = screen.getAllByRole('row')[1] as HTMLElement
    expect(within(row).getAllByText('—')).toHaveLength(1)
  })

  it('shows a dash where the call never stated a member', async () => {
    // A real corpus call: the agent asks for the member ID and never gets it.
    // Absence is a fact about the call, not a gap to fill.
    stubCalls(page([call({ member_id: null })]))
    renderCalls()

    await screen.findByText('F0006')
    const row = screen.getAllByRole('row')[1] as HTMLElement
    expect(within(row).getAllByText('—')).toHaveLength(1)
  })

  it('names the member beside their identifier', async () => {
    stubCalls(page([call()]))
    renderCalls()

    await screen.findByText('F0006')
    expect(screen.getByText('Terrence Boyd')).toBeInTheDocument()
    // The identifier stays: it is what this column's link filters on, and what
    // the member is looked up by elsewhere.
    expect(screen.getByText('CHM6672290')).toBeInTheDocument()
  })

  it('shows the identifier alone when the call never named the member', async () => {
    // A third of the corpus summarises the caller instead of naming them.
    stubCalls(page([call({ member_name: null })]))
    renderCalls()

    await screen.findByText('F0006')
    expect(screen.getByText('CHM6672290')).toBeInTheDocument()
    expect(screen.queryByText('Terrence Boyd')).not.toBeInTheDocument()
  })

  it('links a member to the rest of their calls', async () => {
    stubCalls(page([call()]))
    renderCalls()

    // The link now carries both the name and the identifier as its text.
    const link = await screen.findByRole('link', { name: /CHM6672290/ })
    expect(link).toHaveAttribute('href', '/calls?member=CHM6672290')
  })

  it('explains a load failure rather than showing an empty table', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderCalls()

    expect(await screen.findByText(/Could not load the call list/)).toBeInTheDocument()
  })

  /** Presses a column heading. Scoped to the header: the quick-filter button
   *  'Score under 65' also starts with 'Score'. */
  async function sortBy(label: string) {
    const header = screen.getByRole('columnheader', { name: new RegExp(`^${label}`) })
    await userEvent.click(within(header).getByRole('button'))
  }

  describe('sorting', () => {
    it('asks the API to sort when a column heading is pressed', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await sortBy('Score')

      await waitFor(() => {
        expect(urls.some((url) => url.includes('sort=score'))).toBe(true)
      })
      expect(urls.at(-1)).toContain('direction=asc')
    })

    it('flips direction when the active column is pressed again', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await sortBy('Score')
      await waitFor(() => {
        expect(urls.some((url) => url.includes('sort=score'))).toBe(true)
      })
      await sortBy('Score')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('direction=desc')
      })
    })

    it('starts a newly chosen column ascending rather than inheriting a direction', async () => {
      // Carrying 'desc' over from an unrelated column reads as a broken sort.
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await sortBy('Score')
      await sortBy('Score')
      await waitFor(() => {
        expect(urls.at(-1)).toContain('direction=desc')
      })
      await sortBy('Agent')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('sort=agent')
      })
      expect(urls.at(-1)).toContain('direction=asc')
    })

    it('tells assistive technology which column is sorted', async () => {
      stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await sortBy('Score')

      await waitFor(() => {
        expect(screen.getByRole('columnheader', { name: /^Score/ })).toHaveAttribute(
          'aria-sort',
          'ascending',
        )
      })
    })
  })

  describe('filter dropdowns', () => {
    it('narrows the query by category', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await userEvent.selectOptions(screen.getByLabelText('Category'), 'billing')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('category=billing')
      })
    })

    it('narrows the query by signal type', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await userEvent.selectOptions(screen.getByLabelText('Signal'), 'clinical_risk')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('signal=clinical_risk')
      })
    })

    it('narrows the query by broker', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await userEvent.selectOptions(screen.getByLabelText('Broker'), 'Marcus Trent')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('broker=Marcus')
      })
    })

    it('drops the parameter entirely when set back to All', async () => {
      // An empty value must not be sent as `category=`, which filters on nothing.
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await userEvent.selectOptions(screen.getByLabelText('Category'), 'billing')
      await waitFor(() => {
        expect(urls.at(-1)).toContain('category=billing')
      })
      await userEvent.selectOptions(screen.getByLabelText('Category'), '')

      await waitFor(() => {
        expect(urls.at(-1)).not.toContain('category')
      })
    })
  })

  describe('filtering to one member', () => {
    it('sends the member to the API', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls('/calls?member=CHM6672290')
      await screen.findByText('F0006')

      await waitFor(() => {
        expect(urls.some((url) => url.includes('member=CHM6672290'))).toBe(true)
      })
    })

    it('shows the member as a clearable filter', async () => {
      stubCalls(page([call()]))
      renderCalls('/calls?member=CHM6672290')

      const chip = await screen.findByRole('button', { name: /Member: CHM6672290/ })
      await userEvent.click(chip)

      expect(screen.queryByRole('button', { name: /Member:/ })).not.toBeInTheDocument()
    })

    it('reports a narrowed count rather than the whole corpus', async () => {
      stubCalls(page([call()], { total: 1 }))
      renderCalls('/calls?member=CHM6672290')

      expect(await screen.findByText(/1 matching call/)).toBeInTheDocument()
    })
  })

  describe('the category column', () => {
    it('shows the human label, not the stored code', async () => {
      // The API sends `claims_eob` because the label belongs to the taxonomy,
      // which can be relabelled without touching stored calls.
      stubCalls(page([call()]))
      renderCalls()

      await screen.findByText('F0006')
      expect(screen.getByRole('cell', { name: 'Claims & EOB' })).toBeInTheDocument()
      expect(screen.queryByRole('cell', { name: 'claims_eob' })).not.toBeInTheDocument()
    })

    it('falls back to the code when the taxonomy does not know it', async () => {
      // A code stored before the taxonomy changed. Showing the raw code is more
      // use than showing an empty cell.
      stubCalls(page([call({ category: 'retired_category' })]))
      renderCalls()

      await screen.findByText('F0006')
      expect(screen.getByRole('cell', { name: 'retired_category' })).toBeInTheDocument()
    })
  })

  describe('the default order', () => {
    it('loads newest first without being asked', async () => {
      // A call history is read from the most recent end; the far end of the
      // corpus is not where anyone starts.
      const urls = stubCalls(page([call()]))
      renderCalls()
      await screen.findByText('F0006')

      await waitFor(() => {
        const listing = urls.find((url) => url.includes('/calls?'))
        expect(listing).toContain('sort=reference')
        expect(listing).toContain('direction=desc')
      })
    })

    it('lets an ascending link override the default', async () => {
      // The default is for an unsorted visit only. A shared link naming asc
      // must not be flipped back to newest first.
      const urls = stubCalls(page([call()]))
      renderCalls('/calls?sort=reference&direction=asc')
      await screen.findByText('F0006')

      await waitFor(() => {
        const listing = urls.find((url) => url.includes('/calls?'))
        expect(listing).toContain('direction=asc')
      })
    })

    it('keeps a sort chosen in the URL rather than resetting it', async () => {
      // The default applies to an unsorted visit only; a shared link must open
      // on the sort it names.
      const urls = stubCalls(page([call()]))
      renderCalls('/calls?sort=score&direction=desc')
      await screen.findByText('F0006')

      await waitFor(() => {
        expect(urls.at(-1)).toContain('sort=score')
      })
      expect(urls.at(-1)).toContain('direction=desc')
    })
  })

  describe('a score band', () => {
    it('sends both bounds to the API', async () => {
      const urls = stubCalls(page([call()]))
      renderCalls('/calls?min_score=70&max_score=79')
      await screen.findByText('F0006')

      await waitFor(() => {
        const listing = urls.at(-1)
        expect(listing).toContain('min_score=70')
        expect(listing).toContain('max_score=79')
      })
    })

    it('shows the band as one filter', async () => {
      stubCalls(page([call()]))
      renderCalls('/calls?min_score=70&max_score=79')

      expect(await screen.findByRole('button', { name: /Score: 70–79/ })).toBeInTheDocument()
    })

    it('clears both bounds together', async () => {
      // Half a range is not a filter anyone chose.
      const urls = stubCalls(page([call()]))
      renderCalls('/calls?min_score=70&max_score=79')

      await userEvent.click(await screen.findByRole('button', { name: /Score: 70–79/ }))

      await waitFor(() => {
        expect(urls.at(-1)).not.toContain('min_score')
      })
      expect(urls.at(-1)).not.toContain('max_score')
    })

    it('counts the band as a narrowing filter', async () => {
      stubCalls(page([call()], { total: 30 }))
      renderCalls('/calls?min_score=70&max_score=79')

      expect(await screen.findByText(/30 matching calls/)).toBeInTheDocument()
    })
  })
})
