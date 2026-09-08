/**
 * The import screen's job is to let a reader distrust the result.
 *
 * A conversion that drops calls still returns 201 and still looks like success,
 * which is exactly how the v5 corpus reached a screen at 82 of 100 calls. So
 * what is tested here is mostly the reporting of absence: that a missing field
 * is named and counted, that a call with no transcript is marked, and that the
 * screen says plainly that the corpus in use was not touched.
 */

import { QueryClient } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { ImportPage } from '@/features/corpus-import/ImportPage'

function call(number: number, overrides: Record<string, unknown> = {}) {
  return {
    number,
    reference: `C${String(number).padStart(4, '0')}`,
    title: `Call ${String(number)}`,
    filename: `call_${String(number).padStart(3, '0')}.md`,
    agent: 'Tiffany',
    caller: 'MEMBER',
    tier: 'GOOD',
    score: 88,
    resolution: 'RESOLVED',
    queue: 'Cost Share & Policy',
    turns: 18,
    has_panel: true,
    broker: null,
    repeat: false,
    ...overrides,
  }
}

const CLEAN_IMPORT = {
  name: 'choice-call-corpus-v6-100',
  directory: 'C:\\repo\\Samples\\imported\\choice-call-corpus-v6-100',
  total: 2,
  calls: [call(1), call(2, { broker: 'Marcus Trent: misstated a waiting period', repeat: true })],
}

/** Routes both endpoints the screen uses, so one stub covers the whole page. */
function stubFetch(importBody: unknown, status = 201) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = init?.method === 'POST' ? importBody : []
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: init?.method === 'POST' ? status : 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }),
  )
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <ImportPage />
    </AppProviders>,
  )
}

async function upload(user: ReturnType<typeof userEvent.setup>) {
  const file = new File(['%PDF-1.7'], 'choice_call_corpus_v6_100.pdf', {
    type: 'application/pdf',
  })
  await user.upload(screen.getByLabelText('Corpus PDF'), file)
  await user.click(screen.getByRole('button', { name: 'Extract calls' }))
}

describe('ImportPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('will not submit until a file is chosen', () => {
    stubFetch(CLEAN_IMPORT)
    renderPage()

    expect(screen.getByRole('button', { name: 'Extract calls' })).toBeDisabled()
  })

  it('reports what was extracted and says the live corpus is untouched', async () => {
    const user = userEvent.setup()
    stubFetch(CLEAN_IMPORT)
    renderPage()

    await upload(user)

    expect(await screen.findByText('Every field came through')).toBeInTheDocument()
    expect(screen.getByText('choice-call-corpus-v6-100')).toBeInTheDocument()
    // The reassurance is the point: an operator has to know a run will still
    // analyse the corpus it analysed before.
    expect(screen.getByText(/nothing points at these files/)).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'C0002' })).toBeInTheDocument()
  })

  it('sends the file as multipart rather than JSON', async () => {
    const user = userEvent.setup()
    stubFetch(CLEAN_IMPORT)
    renderPage()

    await upload(user)
    await screen.findByText('Every field came through')

    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
    expect(post?.[1]?.body).toBeInstanceOf(FormData)
    // Setting Content-Type by hand loses the boundary and the server answers a
    // 422 that mentions a missing field rather than the header.
    expect(post?.[1]?.headers).not.toHaveProperty('Content-Type')
  })

  it('counts missing fields instead of leaving empty cells to be noticed', async () => {
    const user = userEvent.setup()
    stubFetch({
      ...CLEAN_IMPORT,
      total: 2,
      calls: [call(1, { agent: null, has_panel: false }), call(2, { agent: null, turns: 1 })],
    })
    renderPage()

    await upload(user)

    expect(await screen.findByText('Some fields did not come through')).toBeInTheDocument()
    expect(screen.getByText('2 calls have no agent name')).toBeInTheDocument()
    expect(screen.getByText('1 call has no authored insights panel')).toBeInTheDocument()
    expect(screen.getByText('1 call has no usable transcript')).toBeInTheDocument()
  })

  it('shows the reason a refused document was refused', async () => {
    const user = userEvent.setup()
    stubFetch(
      {
        type: 'about:blank',
        title: '18 of 100 calls have no transcript.',
        status: 422,
        detail: 'Calls [51, 52, 53] were found but no speaker turns were read from them.',
        code: 'validation_error',
        correlation_id: 'abc123',
      },
      422,
    )
    renderPage()

    await upload(user)

    // The count and the call numbers both matter: they are what says which part
    // of the header changed shape.
    expect(await screen.findByText('18 of 100 calls have no transcript.')).toBeInTheDocument()
    expect(screen.getByText(/\[51, 52, 53\]/)).toBeInTheDocument()
  })

  it('lists previously imported corpora', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              init?.method === 'POST'
                ? CLEAN_IMPORT
                : [{ name: 'v6-100', directory: 'C:\\repo\\Samples\\imported\\v6-100', files: 100 }],
            ),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
      ),
    )
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('v6-100')).toBeInTheDocument()
    })
    expect(screen.getByText('100 files')).toBeInTheDocument()
  })
})
