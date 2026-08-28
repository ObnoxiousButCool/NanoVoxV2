import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from '@/app/layout/AppShell'
import { AppProviders } from '@/app/providers'

const HEALTHY = {
  status: 'up',
  application: 'NanoVox',
  version: '0.1.0',
  environment: 'local',
  checked_at: '2026-08-28T12:00:00Z',
  components: [],
}

function renderShell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={['/analyze']}>
        <AppShell>
          <h1>Content</h1>
        </AppShell>
      </MemoryRouter>
    </AppProviders>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(HEALTHY), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AppShell', () => {
  it('renders the rail expanded by default', () => {
    renderShell()

    expect(screen.getByRole('link', { name: 'Analyze new' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Collapse navigation' })).toBeInTheDocument()
  })

  it('collapses to icons when the toggle is pressed', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }))

    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
  })

  it('keeps every link nameable while collapsed', async () => {
    // An icon nobody can identify is not a smaller menu, it is a worse one.
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }))

    expect(screen.getByRole('link', { name: 'Analyze new' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Diagnostics' })).toBeInTheDocument()
  })

  it('expands again when toggled back', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }))
    await user.click(screen.getByRole('button', { name: 'Expand navigation' }))

    expect(screen.getByRole('button', { name: 'Collapse navigation' })).toBeInTheDocument()
  })

  it('remembers the collapsed choice between visits', async () => {
    const user = userEvent.setup()
    const first = renderShell()

    await user.click(screen.getByRole('button', { name: 'Collapse navigation' }))
    first.unmount()
    renderShell()

    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
  })

  it('marks the current route for assistive technology', () => {
    renderShell()

    expect(screen.getByRole('link', { name: 'Analyze new' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('shows backend health in the rail', async () => {
    renderShell()

    expect(await screen.findByText(/on-prem/)).toBeInTheDocument()
  })

  it('says so when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderShell()

    expect(await screen.findByText(/Backend unreachable/)).toBeInTheDocument()
  })

  it('renders its children', () => {
    renderShell()

    expect(screen.getByRole('heading', { name: 'Content' })).toBeInTheDocument()
  })
})
