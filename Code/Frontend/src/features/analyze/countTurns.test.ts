import { describe, expect, it } from 'vitest'

import { countTurns, hasSpeakerPrefixes } from '@/features/analyze/countTurns'

// The same extract the backend's parser tests use, so the two cannot disagree.
const CORPUS_EXTRACT = `Agent Brad: Choice Administrators, Brad.
Member: Hello. I wanted to ask what my emergency room copay is.
Agent Brad: ER copay is $250, waived if you're admitted.`

describe('countTurns', () => {
  it('counts one turn per speaker prefix', () => {
    expect(countTurns(CORPUS_EXTRACT)).toBe(3)
  })

  it('treats a wrapped continuation as part of the turn above', () => {
    // Must agree with the backend, or the box says 12 and the analysis says 6.
    const wrapped = `Member: I've had this pressure in my chest since last night
and my daughter thinks I should go in.`

    expect(countTurns(wrapped)).toBe(1)
  })

  it('ignores blank lines', () => {
    expect(countTurns('Agent: One.\n\n\nMember: Two.')).toBe(2)
  })

  it('counts nothing when there are no prefixes', () => {
    expect(countTurns('Just a wall of text with no speaker prefixes.')).toBe(0)
    expect(hasSpeakerPrefixes('Just a wall of text')).toBe(false)
  })

  it('counts nothing for empty input', () => {
    expect(countTurns('')).toBe(0)
    expect(countTurns('   \n  ')).toBe(0)
  })

  it('does not mistake prose containing a colon for a new turn', () => {
    const line = 'Agent: and then I explained the policy in detail: it was long.'

    expect(countTurns(line)).toBe(1)
  })
})
