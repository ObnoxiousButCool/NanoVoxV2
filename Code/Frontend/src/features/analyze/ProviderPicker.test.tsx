/**
 * The picker's own behaviour, tested where it lives.
 *
 * These cases used to sit in `AnalyzePage.test.tsx`, which no longer shows a
 * picker — that screen runs on the configured provider. The component is still
 * used by the corpus screen, and the rules it enforces are its own rather than
 * either page's, so they are tested against the component directly.
 */

import { QueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { ProviderPicker, type ProviderSelection } from '@/features/analyze/ProviderPicker'

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
    {
      // A second *usable* provider, so switching between them is testable.
      name: 'anthropic',
      model: 'claude-opus-5',
      configured: true,
      reachable: true,
      implemented: true,
      selectable: true,
      is_default: false,
      detail: null,
    },
  ],
}

/** The picker is controlled, so a caller has to hold its selection. */
function Harness() {
  const [selection, setSelection] = useState<ProviderSelection>({ provider: null, model: null })
  return <ProviderPicker selection={selection} onChange={setSelection} disabled={false} />
}

function renderPicker() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <Harness />
    </AppProviders>,
  )
}

describe('ProviderPicker', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(PROVIDERS), {
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

  it('lists unusable providers with the reason rather than hiding them', async () => {
    // A choice that silently vanished tells the user nothing; "OPENAI_API_KEY is
    // not set" tells them exactly what to do.
    renderPicker()

    const openai = await screen.findByRole('option', { name: /openai/ })

    expect(openai).toBeDisabled()
    expect(openai).toHaveTextContent('unavailable')
  })

  it('shows the model but offers no way to type one', async () => {
    // A typo here would reach the API as a real model name.
    renderPicker()

    await screen.findByRole('option', { name: /ollama/ })

    expect(screen.getByText('qwen2.5:7b-instruct')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Model' })).not.toBeInTheDocument()
  })

  it('shows the model of whichever provider is chosen', async () => {
    const user = userEvent.setup()
    renderPicker()

    await screen.findByRole('option', { name: /ollama/ })
    await user.selectOptions(screen.getByLabelText('Provider'), 'anthropic')

    expect(await screen.findByText('claude-opus-5')).toBeInTheDocument()
  })
})
