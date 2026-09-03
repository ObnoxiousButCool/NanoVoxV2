import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from '@/app/layout/AppShell'
import { providerStatus } from '@/app/layout/providerStatus'
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
    vi.fn((url: string) =>
      Promise.resolve(
        new Response(JSON.stringify(url.includes('/providers') ? PROVIDERS : HEALTHY), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

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
    expect(screen.getByRole('link', { name: 'Brokers' })).toBeInTheDocument()
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

  it('leaves the hidden screens out of the rail', async () => {
    // Hidden entries keep their routes; they are simply not offered here.
    renderShell()

    await screen.findByRole('link', { name: 'Overview' })
    expect(screen.queryByRole('link', { name: 'Corpus run' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Diagnostics' })).not.toBeInTheDocument()
  })

  it('shows no status block at all', async () => {
    // Hidden, not removed: SHOW_RAIL_STATUS in providerStatus.ts brings back the
    // dot and both lines. The rail is navigation only until it does.
    renderShell()

    await screen.findByRole('link', { name: 'Overview' })
    expect(screen.queryByText(/Backend healthy/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Backend unreachable/)).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('stays navigation-only even when the backend is down', async () => {
    // The block is hidden by choice, not by health: an unreachable API must not
    // make it reappear.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderShell()

    await screen.findByRole('link', { name: 'Overview' })
    expect(screen.queryByText(/Backend unreachable/)).not.toBeInTheDocument()
  })

  it('renders its children', () => {
    renderShell()

    expect(screen.getByRole('heading', { name: 'Content' })).toBeInTheDocument()
  })
})

/**
 * The wording behind the hidden indicator.
 *
 * Tested directly rather than through the rail: hiding it must not stop it being
 * correct, because SHOW_PROVIDER_STATUS puts it straight back on screen. The
 * defect these guard against is the original one — a reassuring claim that was
 * false for every cloud provider.
 */
describe('providerStatus', () => {
  it('says transcripts stay put when the model runs on-prem', () => {
    const status = providerStatus(PROVIDERS)

    expect(status.headline).toBe('ollama · on-prem')
    expect(status.detail).toBe('Transcripts stay in this environment')
  })

  it('names the destination when the provider is a cloud one', () => {
    const status = providerStatus({ ...PROVIDERS, default: 'openai' })

    expect(status.headline).toBe('openai · cloud')
    expect(status.detail).toBe('Transcripts are sent to openai')
  })

  it('claims nothing while the provider is unknown', () => {
    // A privacy guarantee that has not been verified must not be stated.
    const status = providerStatus(undefined)

    expect(status.headline).toBe('Checking provider…')
    expect(status.detail).not.toMatch(/stay in this environment/)
  })

  it('claims nothing when the default names no known provider', () => {
    const status = providerStatus({ default: 'ollama', providers: [] })

    expect(status.headline).toBe('Checking provider…')
  })
})
