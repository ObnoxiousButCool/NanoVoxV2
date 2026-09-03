import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from '@/app/App'
import { AppProviders } from '@/app/providers'

const HEALTHY = {
  status: 'up',
  application: 'NanoVox',
  version: '0.1.0',
  environment: 'local',
  checked_at: '2026-08-28T12:00:00Z',
  components: [],
}

/** A dashboard with nothing in it — enough for Overview to render its shell. */
const EMPTY_OVERVIEW = {
  metrics: { total_calls: 0 },
  histogram: { bins: [], total: 0, below_threshold_count: 0, peak: 0 },
  categories: [],
  attention: [],
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

const PROVIDERS = {
  default: 'ollama',
  providers: [
    {
      name: 'ollama',
      model: 'qwen2.5:7b-instruct',
      configured: true,
      reachable: true,
      implemented: true,
      selectable: true,
      is_default: true,
      billable: false,
      local: true,
      detail: null,
    },
    {
      name: 'openai',
      model: 'gpt-4o-mini',
      configured: true,
      reachable: true,
      implemented: true,
      selectable: true,
      is_default: false,
      billable: true,
      local: false,
      detail: null,
    },
  ],
}

function renderAt(path: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/providers')) return Promise.resolve(json(PROVIDERS))
      return Promise.resolve(json(url.includes('/dashboard') ? EMPTY_OVERVIEW : HEALTHY))
    }),
  )

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </AppProviders>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('renders diagnostics at its own route', () => {
    renderAt('/diagnostics')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Diagnostics')
  })

  it('lands an unknown route on the Overview', async () => {
    // Overview itself redirects the eye to Analyze while nothing is analysed,
    // so a fresh install still gets somewhere it can act — see OverviewPage.test.
    renderAt('/somewhere-that-does-not-exist')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'What needs attention',
    )
  })

  it('renders the navigation rail around every screen', () => {
    renderAt('/diagnostics')

    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
  })
})
