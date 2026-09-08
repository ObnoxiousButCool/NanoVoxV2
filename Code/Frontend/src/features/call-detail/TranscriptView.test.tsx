import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { Marker, Turn } from '@/shared/api/types'
import { TranscriptView } from './TranscriptView'

const TURNS: Turn[] = [
  { seq: 0, role: 'AGENT', text: 'Choice Administrators, Sarah speaking.', speaker_name: 'Sarah' },
  {
    seq: 1,
    role: 'MEMBER',
    text: 'Why am I paying anything, let alone $340? Member ID CB-8819204.',
    speaker_name: null,
  },
]

function renderTranscript(markers: Marker[] = []) {
  render(<TranscriptView turns={TURNS} markers={markers} />)
}

describe('TranscriptView', () => {
  it('masks a card number the member read out loud', () => {
    renderTranscript()

    expect(screen.getByText(/Member ID CB-•••9204/)).toBeInTheDocument()
    expect(screen.queryByText(/8819204/)).not.toBeInTheDocument()
  })

  it('leaves the money in the same turn alone', () => {
    // Masking anything numeric would swallow the figure the call is about.
    renderTranscript()

    expect(screen.getByText(/\$340/)).toBeInTheDocument()
  })

  it('still highlights a quote that runs through the masked digits', () => {
    // The reason masking preserves length. Ranges are found in the stored text;
    // if the mask resized the line, this highlight would land on the wrong words.
    renderTranscript([
      {
        polarity: 'NEGATIVE',
        dimension: 'empathy',
        description: 'Did not acknowledge the cost.',
        evidence_turn_seq: 1,
        quote: 'let alone $340? Member ID CB-8819204.',
      },
    ])

    const marked = screen.getByText(/let alone \$340\? Member ID CB-•••9204\./)

    expect(marked.tagName).toBe('MARK')
  })
})
