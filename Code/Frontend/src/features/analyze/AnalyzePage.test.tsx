import { QueryClient } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { AnalyzePage } from '@/features/analyze/AnalyzePage'

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
      detail: null,
    },
    {
      name: 'openai',
      model: 'gpt-4o-mini',
      configured: false,
      reachable: false,
      implemented: true,
      selectable: false,
      is_default: false,
      detail: "Provider 'openai' was selected but OPENAI_API_KEY is not set.",
    },
  ],
}

const TRANSCRIPT = 'Agent Brad: Choice Administrators.\nMember: I have a question.'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** The shape our client always calls fetch with: a string URL plus an init. */
type FetchCall = [url: string, init: RequestInit]

/** Answers `/providers` from the fixture and `/analyses` from `onAnalyse`. */
function stubApi(onAnalyse: () => Promise<Response>) {
  const fetchFn = vi.fn((url: string) => {
    if (url.includes('/providers')) {
      return Promise.resolve(json(PROVIDERS))
    }
    if (url.includes('/analyses')) {
      return onAnalyse()
    }
    return Promise.resolve(json({}))
  })
  vi.stubGlobal('fetch', fetchFn)
  return fetchFn
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={['/analyze']}>
        <Routes>
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/calls/:callId" element={<h1>Call detail</h1>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  )
}

beforeEach(() => {
  stubApi(() => Promise.resolve(json({ id: 7 }, 201)))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AnalyzePage', () => {
  it('counts turns as the user types', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)

    expect(screen.getByRole('status')).toHaveTextContent('2 turns detected')
  })

  it('will not submit text without speaker prefixes', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), 'just a wall of text')

    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled()
    expect(screen.getByText(/No speaker prefixes found/)).toBeInTheDocument()
  })

  it('will not submit an empty transcript', () => {
    renderPage()

    expect(screen.getByRole('button', { name: 'Analyze' })).toBeDisabled()
  })

  it('lists unusable providers with the reason rather than hiding them', async () => {
    renderPage()

    const openai = await screen.findByRole('option', { name: /openai/ })
    expect(openai).toBeDisabled()
    expect(openai).toHaveTextContent('unavailable')
  })

  it('warns that a local run takes minutes', async () => {
    const user = userEvent.setup()
    stubApi(() => new Promise(() => undefined))
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(await screen.findByText(/takes several minutes/)).toBeInTheDocument()
  })

  it('opens the new call once the analysis completes', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(await screen.findByRole('heading', { name: 'Call detail' })).toBeInTheDocument()
  })

  it('sends the chosen provider and model', async () => {
    const user = userEvent.setup()
    const fetchFn = stubApi(() => Promise.resolve(json({ id: 7 }, 201)))
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)
    await screen.findByRole('option', { name: /ollama/ })
    await user.type(screen.getByLabelText('Model'), 'llama3.1:latest')
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    await waitFor(() => {
      const calls = fetchFn.mock.calls as unknown as FetchCall[]
      const call = calls.find(([url]) => url.includes('/analyses'))
      expect(call).toBeDefined()
      const body = JSON.parse((call?.[1].body as string | undefined) ?? '{}') as Record<
        string,
        unknown
      >
      expect(body['provider']).toBe('ollama')
      expect(body['model']).toBe('llama3.1:latest')
    })
  })

  it('explains a failed analysis with its correlation id', async () => {
    const user = userEvent.setup()
    stubApi(() =>
      Promise.resolve(
        json(
          {
            type: 'about:blank',
            title: 'Ollama could not be reached.',
            status: 503,
            detail: 'Is the server running?',
            code: 'provider_unavailable',
            correlation_id: 'trace-9',
          },
          503,
        ),
      ),
    )
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)
    await user.click(screen.getByRole('button', { name: 'Analyze' }))

    expect(await screen.findByText(/Ollama could not be reached/)).toBeInTheDocument()
    expect(screen.getByText(/trace-9/)).toBeInTheDocument()
  })

  it('clears the box and any previous error', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByLabelText('Transcript'), TRANSCRIPT)
    await user.click(screen.getByRole('button', { name: 'Clear' }))

    expect(screen.getByLabelText('Transcript')).toHaveValue('')
    expect(screen.getByRole('status')).toHaveTextContent('0 turns detected')
  })
})
