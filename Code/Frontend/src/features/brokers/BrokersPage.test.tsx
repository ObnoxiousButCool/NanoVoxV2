import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { BrokersPage } from '@/features/brokers/BrokersPage'

const MARCUS = {
  broker_name: 'Marcus Trent',
  signals: 3,
  positive: 0,
  negative: 3,
  is_net_positive: false,
  call_references: ['F0008', 'F0009', 'F0010'],
}

const PATRICIA = {
  broker_name: 'Patricia Nunez',
  signals: 2,
  positive: 2,
  negative: 0,
  is_net_positive: true,
  call_references: ['F0004', 'F0005'],
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderBrokers(brokers: unknown[] = [MARCUS, PATRICIA]) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json(brokers))))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter>
        <BrokersPage />
      </MemoryRouter>
    </AppProviders>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('BrokersPage', () => {
  it('states the attribution rule on the screen that names people', async () => {
    renderBrokers()

    expect(await screen.findByText('How attribution works')).toBeInTheDocument()
    expect(screen.getByText(/Nothing is inferred/)).toBeInTheDocument()
  })

  it('separates a conduct case from a broker who scores well', async () => {
    // Net scoring is the whole point: one error is coaching, not conduct.
    renderBrokers()

    expect(await screen.findByText('Conduct review')).toBeInTheDocument()
    expect(screen.getByText('Best practice')).toBeInTheDocument()
  })

  it('says what a negative broker was reported for', async () => {
    renderBrokers()

    expect(
      await screen.findByText('3 of 3 signals record a failure members reported themselves.'),
    ).toBeInTheDocument()
  })

  it('shows the positive and negative split behind the total', async () => {
    // A bare "3" hides whether it is three complaints or three compliments.
    renderBrokers()

    await screen.findByText('Marcus Trent')
    expect(screen.getByText(/0 POSITIVE/)).toBeInTheDocument()
    expect(screen.getByText(/2 POSITIVE/)).toBeInTheDocument()
  })

  it('links every broker to the calls that produced their signals', async () => {
    renderBrokers()

    await screen.findByText('Marcus Trent')
    for (const reference of [...MARCUS.call_references, ...PATRICIA.call_references]) {
      expect(screen.getByText(reference)).toBeInTheDocument()
    }
  })

  it('counts the signals and the brokers in the subtitle', async () => {
    renderBrokers()

    expect(await screen.findByText('5 signals across 2 named brokers.')).toBeInTheDocument()
  })

  it('shows an empty result as a result rather than omitting the screen', async () => {
    renderBrokers([])

    expect(await screen.findByText('No broker signals recorded')).toBeInTheDocument()
    expect(screen.getByText(/omitted, so the absence is visible/)).toBeInTheDocument()
  })

  it('explains a load failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <AppProviders client={client}>
        <MemoryRouter>
          <BrokersPage />
        </MemoryRouter>
      </AppProviders>,
    )

    expect(await screen.findByText(/Could not load the broker scorecard/)).toBeInTheDocument()
  })
})
