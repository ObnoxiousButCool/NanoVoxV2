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

function renderAt(path: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(HEALTHY), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
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

  it('lands on Analyze, the only screen a fresh install can act on', () => {
    // Nothing has been analysed yet, so a dashboard would be an empty room.
    renderAt('/somewhere-that-does-not-exist')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Analyze a call')
  })

  it('renders the navigation rail around every screen', () => {
    renderAt('/diagnostics')

    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
  })
})
