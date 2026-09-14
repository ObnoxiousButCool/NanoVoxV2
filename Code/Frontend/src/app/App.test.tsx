import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

/** No member showing a warning sign — enough for Inferences to render its shell. */
const EMPTY_MEMBERS_AT_RISK = {
  basis: 'Observed warning signs, not a prediction.',
  factor_vocabulary: [],
  members: [],
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
      // Checked before the general /dashboard case below: this route also
      // contains "/dashboard" in its path, and needs its own response shape.
      if (url.includes('/members-at-risk')) return Promise.resolve(json(EMPTY_MEMBERS_AT_RISK))
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
    // Overview itself redirects the eye to Analyze while nothing is analyzed,
    // so a fresh install still gets somewhere it can act — see OverviewPage.test.
    renderAt('/somewhere-that-does-not-exist')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'Operations dashboard',
    )
  })

  it('renders the navigation rail around every screen', () => {
    renderAt('/diagnostics')

    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
  })

  it('scrolls back to the top when navigating to a new screen', async () => {
    // A reader who scrolled partway down Dashboard should not land mid-page
    // on Inferences — each screen starts where a reader expects, at its top.
    const user = userEvent.setup()
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)
    renderAt('/overview')

    await user.click(await screen.findByRole('link', { name: 'Inferences' }))

    expect(scrollTo).toHaveBeenCalledWith(0, 0)
  })
})
