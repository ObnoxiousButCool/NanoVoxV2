import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { DiagnosticsPage } from '@/features/diagnostics/DiagnosticsPage'

const HEALTHY = {
  status: 'up',
  application: 'NanoVox',
  version: '0.1.0',
  environment: 'local',
  checked_at: '2026-08-28T12:00:00Z',
  components: [{ name: 'database', status: 'up', detail: null }],
}

function renderPage() {
  // Retries off: a test asserting the error state should not wait for backoff.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <DiagnosticsPage />
    </AppProviders>,
  )
}

function mockFetch(body: unknown, init: ResponseInit = {}) {
  const fetchFn = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
      ...init,
    }),
  )
  vi.stubGlobal('fetch', fetchFn)
  return fetchFn
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DiagnosticsPage', () => {
  it('shows a loading state before the first response', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => undefined)))

    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('Checking…')
  })

  it('renders each component of a healthy report', async () => {
    mockFetch(HEALTHY)

    renderPage()

    expect(await screen.findByText('database')).toBeInTheDocument()
    expect(screen.getAllByText('UP').length).toBeGreaterThan(0)
    expect(screen.getByText('local')).toBeInTheDocument()
  })

  it('renders a 503 report rather than treating it as an error', async () => {
    // The backend answers 503 when a component is down; the body is still the
    // report, and it is exactly what this page exists to show.
    mockFetch(
      {
        ...HEALTHY,
        status: 'down',
        components: [{ name: 'database', status: 'down', detail: 'OperationalError' }],
      },
      { status: 503 },
    )

    renderPage()

    expect(await screen.findByText('OperationalError', { exact: false })).toBeInTheDocument()
    expect(screen.getAllByText('DOWN').length).toBeGreaterThan(0)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('explains an unreachable backend instead of showing a blank card', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Cannot reach the NanoVox API')
    expect(alert).toHaveTextContent('VITE_API_BASE_URL')
  })

  it('surfaces the correlation ID from a problem response', async () => {
    mockFetch(
      {
        type: 'about:blank',
        title: 'Service Unavailable',
        status: 500,
        detail: 'An unexpected error occurred.',
        code: 'internal_error',
        correlation_id: 'trace-42',
      },
      { status: 500 },
    )

    renderPage()

    expect(await screen.findByText(/trace-42/)).toBeInTheDocument()
  })

  it('states plainly when the backend declares no dependencies', async () => {
    mockFetch({ ...HEALTHY, components: [] })

    renderPage()

    expect(await screen.findByText(/declares no dependencies/)).toBeInTheDocument()
  })
})
