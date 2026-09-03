import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppProviders } from '@/app/providers'
import { CallDetailPage } from '@/features/call-detail/CallDetailPage'
import type { Analysis } from '@/shared/api/types'

/** Call #89 as the API returns it. */
const CALL_89: Analysis = {
  id: 1,
  reference: 'C0001',
  title: 'ER copay question that was a cardiac presentation',
  summary: 'The member asked which setting cost less, then disclosed chest pressure.',
  category: 'coverage_benefits',
  category_label: 'Coverage & Benefits',
  resolution: 'UNRESOLVED',
  sentiment_start: 'WORRIED',
  sentiment_end: 'DISMISSED',
  agent_name: 'Brad',
  member_context: 'Member aged 68 on a CalChoice HMO plan.',
  duration_minutes: 6,
  source: 'PASTED',
  signal_codes: ['clinical_risk'],
  score: {
    value: 27,
    status: 'provisional',
    tier: 'POOR',
    total_positive: 2,
    total_negative: 75,
    applied_offset: 2,
    gate_messages: ['Score withheld pending clinical review.'],
  },
  markers: [
    {
      polarity: 'NEGATIVE',
      dimension: 'escalation_appropriateness',
      description: 'Did not recognise chest pressure as an emergency.',
      evidence_turn_seq: 1,
      quote: 'pressure in my chest',
    },
  ],
  rejected_marker_notes: ['Quoted text does not appear in turn 4: "never said this"'],
  rejected_attribution_notes: [],
  l4_signals: [
    {
      category: 'compliance_risk',
      owner: 'Compliance',
      severity: 'CRITICAL',
      narrative: 'Cost information influenced a care-setting decision.',
      recommended_action: 'Contact this member for a welfare check.',
    },
  ],
  broker_signals: [],
  assist_events: [
    {
      outcome: 'SHOULD_HAVE_FIRED',
      trigger: 'Symptom keywords with member age 68',
      recommendation: 'Mandatory nurse line transfer.',
      severity: 'CRITICAL',
      at_turn_seq: 1,
      timestamp_label: '2:30',
      is_gap: true,
    },
  ],
  layers: [
    { layer: 'L1', payload: { call_type: 'ER copay inquiry', agent_tone: 'transactional' } },
    { layer: 'L2', payload: { topics: ['triage', 'cost steering'] } },
    { layer: 'L3', payload: {} },
    { layer: 'L4', payload: {} },
    { layer: 'L5', payload: {} },
  ],
  transcript: [
    { seq: 0, role: 'AGENT', speaker_name: 'Brad', text: 'Choice Administrators, Brad.' },
    {
      seq: 1,
      role: 'MEMBER',
      speaker_name: null,
      text: "I've had this pressure in my chest since last night.",
    },
  ],
  provenance: {
    provider: 'ollama',
    model: 'qwen2.5:7b-instruct',
    prompt_version: '1.0.0',
    rubric_version: '1.0.0',
    analysed_at: '2026-08-28T12:00:00Z',
    input_tokens: 2880,
    output_tokens: 1273,
    duration_ms: 242800,
  },
}

function renderCall(analysis: Analysis = CALL_89) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(analysis), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={['/calls/1']}>
        <Routes>
          <Route path="/calls/:callId" element={<CallDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CallDetailPage', () => {
  it('shows a withheld score with its number and its reason', async () => {
    // Hiding the number would leave a reviewer unable to judge urgency while
    // the call waits for clinical sign-off.
    renderCall()

    expect(await screen.findByText('27')).toBeInTheDocument()
    expect(
      screen.getAllByText(/Score withheld pending clinical review/).length,
    ).toBeGreaterThan(0)
  })

  it('renders all five layers', async () => {
    renderCall()

    await screen.findByText('27')
    for (const title of [
      'Transcription & understanding',
      'What happened',
      'How well it was handled',
      'What to do about it',
      'Real-time assist',
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }
  })

  it('shows each observation with the turn and words it rests on', async () => {
    renderCall()

    await screen.findByText('27')
    expect(screen.getByText(/Did not recognise chest pressure/)).toBeInTheDocument()
    expect(screen.getByText(/turn 1:/)).toBeInTheDocument()
  })

  it('highlights the quoted evidence in the transcript', async () => {
    renderCall()

    await screen.findByText('27')
    const marks = document.querySelectorAll('mark')
    expect(marks).toHaveLength(1)
    expect(marks[0]?.textContent).toBe('pressure in my chest')
  })

  it('reports discarded observations rather than hiding them', async () => {
    renderCall()

    await screen.findByText('27')
    expect(screen.getByText(/1 observation was discarded/)).toBeInTheDocument()
  })

  it('presents a missed assist as a gap, not an empty state', async () => {
    renderCall()

    await screen.findByText('27')
    expect(screen.getByText(/Did not trigger · 2:30/)).toBeInTheDocument()
    expect(screen.getByText(/the absence is the finding/)).toBeInTheDocument()
  })

  it('names the team that owns each operational finding', async () => {
    renderCall()

    await screen.findByText('27')
    expect(screen.getByText(/Owner: Compliance/)).toBeInTheDocument()
  })

  it('shows the provenance behind the analysis', async () => {
    renderCall()

    await screen.findByText('27')
    expect(screen.getByText('qwen2.5:7b-instruct')).toBeInTheDocument()
  })

  it('distinguishes a layer that failed from one that found nothing', async () => {
    // "L5 unavailable" is a fault; "nothing triggered" is a finding. Drawing them
    // the same way would hide a broken pipeline.
    renderCall({
      ...CALL_89,
      assist_events: [],
      layers: [
        ...CALL_89.layers.slice(0, 4),
        { layer: 'L5', payload: { unavailable: true, reason: 'Model would not comply.' } },
      ],
    })

    await screen.findByText('27')
    expect(screen.getByText(/L5 could not be produced/)).toBeInTheDocument()
    expect(screen.getByText(/This is a failure, not an empty result/)).toBeInTheDocument()
  })

  it('says so plainly when a layer genuinely found nothing', async () => {
    renderCall({ ...CALL_89, assist_events: [], l4_signals: [] })

    await screen.findByText('27')
    expect(screen.getByText(/No assist activity was recorded/)).toBeInTheDocument()
    expect(screen.queryByText(/could not be produced/)).not.toBeInTheDocument()
  })

  it('explains a load failure instead of showing a blank page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <AppProviders client={client}>
        <MemoryRouter initialEntries={['/calls/1']}>
          <Routes>
            <Route path="/calls/:callId" element={<CallDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AppProviders>,
    )

    expect(await screen.findByText(/Could not load this call/)).toBeInTheDocument()
  })

  describe('collapsible layers', () => {
    it('starts every layer open', async () => {
      // A collapsed default would hide the analysis behind a click on first
      // sight, and the evidence being readable is the point of the page.
      renderCall()

      await screen.findByRole('button', { name: /Transcription & understanding/ })
      for (const title of [
        'Transcription & understanding',
        'What happened',
        'How well it was handled',
        'What to do about it',
        'Real-time assist',
      ]) {
        expect(screen.getByRole('button', { name: new RegExp(title) })).toHaveAttribute(
          'aria-expanded',
          'true',
        )
      }
    })

    it('gives the transcript a toggle too', async () => {
      // It had none: it was a hand-rolled copy of the layer markup, so the
      // toggle added to LayerBlock never reached it.
      renderCall()

      // "Transcript" alone also matches "Transcription & understanding".
      const transcript = await screen.findByRole('button', {
        name: /turns · speaker separated/,
      })
      expect(transcript).toHaveAttribute('aria-expanded', 'true')

      await userEvent.click(transcript)

      expect(transcript).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByText(/turns · speaker separated/)).toBeInTheDocument()
    })

    it('closes one layer without touching the others', async () => {
      renderCall()

      const l1 = await screen.findByRole('button', { name: /Transcription & understanding/ })
      await userEvent.click(l1)

      expect(l1).toHaveAttribute('aria-expanded', 'false')
      expect(
        screen.getByRole('button', { name: /How well it was handled/ }),
      ).toHaveAttribute('aria-expanded', 'true')
    })

    it('opens again when pressed a second time', async () => {
      renderCall()

      const l2 = await screen.findByRole('button', { name: /What happened/ })
      await userEvent.click(l2)
      await userEvent.click(l2)

      expect(l2).toHaveAttribute('aria-expanded', 'true')
    })

    it('remembers what was collapsed on the next call opened', async () => {
      // The layer someone reads is a habit, not a property of one call.
      const first = renderCall()
      await userEvent.click(
        await screen.findByRole('button', { name: /Real-time assist/ }),
      )
      first.unmount()

      renderCall()

      expect(
        await screen.findByRole('button', { name: /Real-time assist/ }),
      ).toHaveAttribute('aria-expanded', 'false')
    })
  })

  describe('getting back to the list', () => {
    it('offers a way back', async () => {
      renderCall()

      expect(await screen.findByText(/Back to calls/)).toBeInTheDocument()
    })

    it('links straight to the list when the call was opened directly', async () => {
      // A bookmark or a pasted URL: there is no history to return through, so a
      // plain link is the only thing that can work.
      renderCall()

      const back = await screen.findByRole('link', { name: /Back to calls/ })
      expect(back).toHaveAttribute('href', '/calls')
    })
  })
})
