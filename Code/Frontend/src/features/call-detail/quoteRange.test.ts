import { describe, expect, it } from 'vitest'

import { findQuoteRange } from '@/features/call-detail/quoteRange'

const TURN = "I've had this pressure in my chest since last night and my arm has been aching."

describe('findQuoteRange', () => {
  it('locates a quote and returns the original character range', () => {
    const range = findQuoteRange(TURN, 'pressure in my chest')

    expect(range).not.toBeNull()
    const [start, end] = range as [number, number]
    expect(TURN.slice(start, end)).toBe('pressure in my chest')
  })

  it('matches across a line wrap, as the backend validator does', () => {
    // Corpus transcripts are hard-wrapped mid-sentence; the stored quote is not.
    const wrapped = "I've had this pressure\n  in my chest since last night."

    const range = findQuoteRange(wrapped, 'pressure in my chest')

    expect(range).not.toBeNull()
    const [start, end] = range as [number, number]
    expect(wrapped.slice(start, end)).toBe('pressure\n  in my chest')
  })

  it('ignores case', () => {
    expect(findQuoteRange(TURN, 'PRESSURE IN MY CHEST')).not.toBeNull()
  })

  it('returns null rather than approximating when the words are absent', () => {
    // Better to highlight nothing than to highlight the wrong words.
    expect(findQuoteRange(TURN, 'I am having a heart attack')).toBeNull()
  })

  it('returns null for an empty quote', () => {
    expect(findQuoteRange(TURN, '   ')).toBeNull()
  })

  it('finds a quote at the very start of a turn', () => {
    const range = findQuoteRange('ER copay is $250, waived if admitted.', 'ER copay is $250')

    expect(range?.[0]).toBe(0)
  })

  it('finds a quote at the very end of a turn', () => {
    const text = 'There is one on Ridgeway'
    const range = findQuoteRange(text, 'on Ridgeway')

    const [start, end] = range as [number, number]
    expect(text.slice(start, end)).toBe('on Ridgeway')
  })
})
