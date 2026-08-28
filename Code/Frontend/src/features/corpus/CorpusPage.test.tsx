import { QueryClient } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { CorpusPage } from '@/features/corpus/CorpusPage'

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
      detail: null,
    },
  ],
}

const STATUS = {
  location: 'C:/corpus (call_*.md)',
  total_calls: 100,
  analysed_calls: 40,
  outstanding: 60,
  active_run_id: null as number | null,
}

function progress(overrides: Record<string, number> = {}) {
  return {
    total: 100,
    completed: 40,
    failed: 0,
    skipped: 0,
    cancelled: 0,
    running: 1,
    pending: 59,
    finished: 40,
    remaining: 60,
    percent_complete: 40,
    ...overrides,
  }
}

function run(overrides: Record<string, unknown> = {}) {
  return {
    id: 3,
    provider: 'ollama',
    model: 'qwen2.5:7b-instruct',
    force: false,
    status: 'RUNNING',
    message: '',
    created_at: '2026-08-28T12:00:00Z',
    started_at: '2026-08-28T12:00:00Z',
    finished_at: null,
    is_active: true,
    can_resume: false,
    progress: progress(),
    items: [
      {
        source_id: 'call_001',
        reference: 'C0001',
        title: 'Prior auth',
        status: 'COMPLETED',
        call_id: 11,
        message: '',
        started_at: null,
        finished_at: null,
        duration_ms: 4200,
      },
      {
        source_id: 'call_002',
        reference: 'C0002',
        title: 'Out-of-pocket maximum',
        status: 'SKIPPED',
        call_id: null,
        message: 'Already analysed. Re-run with force to replace it.',
        started_at: null,
        finished_at: null,
        duration_ms: null,
      },
      {
        source_id: 'call_003',
        reference: 'C0003',
        title: 'Claims',
        status: 'RUNNING',
        call_id: null,
        message: '',
        started_at: null,
        finished_at: null,
        duration_ms: null,
      },
    ],
    ...overrides,
  }
}

class FakeEventSource {
  static instances: FakeEventSource[] = []
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(readonly url: string) {
    FakeEventSource.instances.push(this)
  }
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {}
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

interface World {
  status: typeof STATUS
  runs: unknown[]
  run: unknown
  posted: { url: string; body: unknown }[]
  startStatus: number
  startBody: unknown
}

function setup(world: Partial<World> = {}) {
  const state: World = {
    status: STATUS,
    // The page shows the newest run when none is active, so the history has to
    // contain it for the panel to be reachable — as it is against a real API.
    runs: [run()],
    run: run(),
    posted: [],
    startStatus: 201,
    startBody: run(),
    ...world,
  }

  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        state.posted.push({ url, body: JSON.parse(String(init.body)) })
        return Promise.resolve(json(state.startBody, state.startStatus))
      }
      if (url.includes('/providers')) return Promise.resolve(json(PROVIDERS))
      if (url.includes('/corpus/runs/')) return Promise.resolve(json(state.run))
      if (url.includes('/corpus/runs')) return Promise.resolve(json(state.runs))
      if (url.includes('/corpus')) return Promise.resolve(json(state.status))
      return Promise.resolve(json({}))
    }),
  )

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <AppProviders client={client}>
      <MemoryRouter>
        <CorpusPage />
      </MemoryRouter>
    </AppProviders>,
  )
  return state
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CorpusPage', () => {
  it('says how much work a run would be before starting one', async () => {
    setup({ runs: [] })

    expect(await screen.findByText('100')).toBeInTheDocument()
    expect(screen.getByText('calls in the corpus')).toBeInTheDocument()
    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('names where the corpus is read from', async () => {
    // A run that read the wrong directory is otherwise invisible.
    setup()

    expect(await screen.findByText('C:/corpus (call_*.md)')).toBeInTheDocument()
  })

  it('starts a run against the chosen provider', async () => {
    const state = setup({ runs: [] })
    await screen.findByText('calls in the corpus')

    await userEvent.click(screen.getByRole('button', { name: 'Analyse the corpus' }))

    await waitFor(() => {
      expect(state.posted).toHaveLength(1)
    })
    expect(state.posted[0]?.url).toContain('/corpus/runs')
  })

  it('asks the backend to replace when force is ticked', async () => {
    const state = setup({ runs: [] })
    await screen.findByText('calls in the corpus')

    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Analyse the corpus' }))

    await waitFor(() => {
      expect(state.posted[0]?.body).toMatchObject({ force: true })
    })
  })

  it('counts the whole corpus once force is ticked', async () => {
    // 60 outstanding becomes 100 to re-analyse; showing 60 would understate it.
    setup()
    await screen.findByText('outstanding')

    await userEvent.click(screen.getByRole('checkbox'))

    expect(await screen.findByText('to re-analyse')).toBeInTheDocument()
  })
})

describe('the cost guard', () => {
  it('says nothing about cost for a local provider', async () => {
    setup()
    await screen.findByText('calls in the corpus')

    expect(screen.queryByText('This run will be charged for')).not.toBeInTheDocument()
  })

  it('warns before a paid provider, in model calls not guesses', async () => {
    setup()
    await screen.findByText('calls in the corpus')

    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')

    expect(await screen.findByText('This run will be charged for')).toBeInTheDocument()
    expect(screen.getByText(/500 model calls/)).toBeInTheDocument()
    // Deliberately no figure: a wrong estimate is worse than none.
    expect(screen.getByText(/wrong estimate would be worse than none/)).toBeInTheDocument()
  })

  it('will not start a paid run until it is acknowledged', async () => {
    setup()
    await screen.findByText('calls in the corpus')
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')

    expect(screen.getByRole('button', { name: 'Analyse the corpus' })).toBeDisabled()
  })

  it('sends the acknowledgement the API requires', async () => {
    const state = setup()
    await screen.findByText('calls in the corpus')
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')

    await userEvent.click(screen.getByLabelText('I understand this run will be billed'))
    await userEvent.click(screen.getByRole('button', { name: 'Analyse the corpus' }))

    await waitFor(() => {
      expect(state.posted[0]?.body).toMatchObject({ acknowledge_cost: true, provider: 'openai' })
    })
  })

  it('withdraws an acknowledgement when the provider changes', async () => {
    // Confirming a bill for one provider is not consent for another.
    setup()
    await screen.findByText('calls in the corpus')
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')
    await userEvent.click(screen.getByLabelText('I understand this run will be billed'))

    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'ollama')
    await userEvent.selectOptions(screen.getByLabelText('Provider'), 'openai')

    expect(screen.getByLabelText('I understand this run will be billed')).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Analyse the corpus' })).toBeDisabled()
  })
})

describe('a run in progress', () => {
  it('shows progress with each outcome counted separately', async () => {
    // "40 done" would hide whether they were analysed or skipped.
    const working = run({ progress: progress({ completed: 30, skipped: 8, failed: 2 }) })
    setup({ run: working, runs: [working] })

    expect(await screen.findByText(/30 analysed/)).toBeInTheDocument()
    expect(screen.getByText(/8 skipped/)).toBeInTheDocument()
    expect(screen.getByText(/2 failed/)).toBeInTheDocument()
  })

  it('exposes progress to assistive technology', async () => {
    setup()

    const bar = await screen.findByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '40')
  })

  it('names the call being analysed and warns it is slow', async () => {
    setup()

    expect(await screen.findByText(/Analysing C0003/)).toBeInTheDocument()
    expect(screen.getByText(/minutes per call/)).toBeInTheDocument()
  })

  it('links a finished call to the analysis it produced', async () => {
    setup()

    const link = await screen.findByRole('link', { name: 'C0001' })
    expect(link).toHaveAttribute('href', '/calls/11')
  })

  it('shows a skipped call with the reason and no link', async () => {
    setup()

    await screen.findByText('C0002')
    expect(screen.getByText(/Already analysed/)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'C0002' })).not.toBeInTheDocument()
  })

  it('refuses a second run while one is working', async () => {
    setup({ status: { ...STATUS, active_run_id: 3 } })

    await screen.findByText('calls in the corpus')
    expect(screen.getByRole('button', { name: 'Analyse the corpus' })).toBeDisabled()
    expect(screen.getByText('A run is already in progress.')).toBeInTheDocument()
  })

  it('cancels through the API rather than just hiding the run', async () => {
    const state = setup({ status: { ...STATUS, active_run_id: 3 } })
    await screen.findByText('calls in the corpus')

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(state.posted[0]?.url).toContain('/corpus/runs/3/cancel')
    })
  })

  it('explains that cancelling waits for the call in flight', async () => {
    const cancelling = run({ status: 'CANCELLING' })
    setup({ run: cancelling, runs: [cancelling] })

    expect(await screen.findByText(/Stopping after the call in flight/)).toBeInTheDocument()
  })
})

describe('a stopped run', () => {
  const stopped = run({
    status: 'INTERRUPTED',
    is_active: false,
    can_resume: true,
    message: 'The process stopped while this run was working.',
    progress: progress({ completed: 40, running: 0, pending: 60, finished: 40 }),
  })

  it('offers to continue it, saying how much is left', async () => {
    setup({ run: stopped, runs: [stopped] })

    expect(await screen.findByRole('button', { name: 'Resume this run' })).toBeInTheDocument()
    expect(screen.getByText(/60 calls still need work/)).toBeInTheDocument()
    expect(screen.getByText(/keeps what is already done/)).toBeInTheDocument()
  })

  it('resumes through the API', async () => {
    const state = setup({ run: stopped, runs: [stopped] })
    await screen.findByRole('button', { name: 'Resume this run' })

    await userEvent.click(screen.getByRole('button', { name: 'Resume this run' }))

    await waitFor(() => {
      expect(state.posted[0]?.url).toContain('/corpus/runs/3/resume')
    })
  })

  it('says why it stopped', async () => {
    setup({ run: stopped, runs: [stopped] })

    expect(await screen.findByText(/The process stopped/)).toBeInTheDocument()
  })

  it('does not offer to resume a completed run', async () => {
    const finished = run({ status: 'COMPLETED', is_active: false, can_resume: false })
    setup({ run: finished, runs: [finished] })

    await screen.findByText('calls in the corpus')
    expect(screen.queryByRole('button', { name: 'Resume this run' })).not.toBeInTheDocument()
  })
})

describe('run history', () => {
  it('lists earlier runs with the model that produced them', async () => {
    // Provenance: which model produced these hundred calls.
    setup({
      runs: [
        {
          id: 3,
          provider: 'ollama',
          model: 'qwen2.5:7b-instruct',
          force: false,
          status: 'COMPLETED',
          message: '',
          created_at: '2026-08-28T12:00:00Z',
          started_at: null,
          finished_at: null,
          is_active: false,
          can_resume: false,
          progress: progress({ completed: 100, finished: 100, remaining: 0 }),
        },
      ],
    })

    // The history row names the model, which is the provenance question a
    // reader of a hundred analysed calls actually asks.
    const row = await screen.findByRole('button', { name: /Run 3/ })
    expect(row).toHaveTextContent('ollama · qwen2.5:7b-instruct')
    expect(row).toHaveTextContent('100/100 analysed')
  })

  it('says so when nothing has ever been run', async () => {
    setup({ runs: [], run: null })

    expect(await screen.findByText('No runs yet')).toBeInTheDocument()
  })

  it('explains a failure to load the corpus', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <AppProviders client={client}>
        <MemoryRouter>
          <CorpusPage />
        </MemoryRouter>
      </AppProviders>,
    )

    expect(await screen.findByText(/Could not load the corpus/)).toBeInTheDocument()
  })
})
