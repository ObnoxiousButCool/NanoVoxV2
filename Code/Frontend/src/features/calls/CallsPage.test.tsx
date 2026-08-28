import { QueryClient } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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
    category: 'coverage_benefits',
    agent_name: 'Brad',
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

/** Records every requested URL so filters can be asserted on the query itself. */
function stubCalls(body: unknown) {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      urls.push(url)
      return Promise.resolve(json(body))
    }),
  )
  return urls
}

function renderCalls() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter>
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
    expect(screen.getByText('Brad')).toBeInTheDocument()
    expect(screen.getByText('UNRESOLVED')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
    expect(screen.getByText('clinical risk')).toBeInTheDocument()
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

    expect(await screen.findByText('—')).toBeInTheDocument()
  })

  it('explains a load failure rather than showing an empty table', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderCalls()

    expect(await screen.findByText(/Could not load the call list/)).toBeInTheDocument()
  })
})
