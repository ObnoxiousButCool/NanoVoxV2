import { describe, expect, it } from 'vitest'

import {
  countTurns,
  hasSpeakerPrefixes,
  inlineSpeakerPrefixes,
  transcriptWarning,
} from '@/features/analyze/countTurns'

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

// The same conversation with its line breaks stripped, as copying flattens it.
const FLATTENED = CORPUS_EXTRACT.split('\n').join(' ')

describe('countTurns, on a flattened paste', () => {
  it('recovers the turns rather than reporting one', () => {
    // Must match the backend, which recovers all fifty corpus transcripts
    // identically when flattened this way.
    expect(countTurns(FLATTENED)).toBe(3)
  })

  it('does not open a turn on a colon inside speech', () => {
    expect(countTurns('Agent Brad: Three things: the date, the code, the amount.')).toBe(1)
  })

  it('does not open a turn on a role mid-sentence', () => {
    expect(countTurns('Agent Brad: I told the member: it was already paid.')).toBe(1)
  })

  it('does not treat a wrapped line carrying an early colon as a speaker', () => {
    // call_017 in the corpus. This produced a phantom agent before the label
    // had to look like one.
    const wrapped = `Agent Sarah: We processed four
new enrollments effective the 1st: two dental only, two dental and vision.`

    expect(countTurns(wrapped)).toBe(1)
  })

  it('trusts a bare name at the start of a line but not inside one', () => {
    expect(countTurns('Brad: Hello there.')).toBe(1)
    expect(countTurns('Agent Brad: Hello. Sarah: Hi.')).toBe(1)
  })
})

describe('transcriptWarning', () => {
  it('says nothing about a well-formed transcript', () => {
    expect(transcriptWarning(CORPUS_EXTRACT)).toBeNull()
  })

  it('says nothing about a flattened transcript the parser recovers', () => {
    // The warning existed for this case. Now that parsing handles it, warning
    // about it would be crying wolf.
    expect(transcriptWarning(FLATTENED)).toBeNull()
    expect(inlineSpeakerPrefixes(FLATTENED)).toBe(0)
  })

  it('warns about bare names on one line, which parsing will not split', () => {
    const bare = 'Sarah: Thank you for calling. Maria: Why do I owe $340? Sarah: Let me check.'

    const warning = transcriptWarning(bare)

    expect(warning).toContain('Only one turn')
    expect(warning).toContain('bare name')
  })

  it('leaves the no-prefix case to the message that already covers it', () => {
    expect(transcriptWarning('Just a wall of text with no speaker prefixes.')).toBeNull()
  })

  it('tolerates one incidental colon rather than crying wolf', () => {
    expect(transcriptWarning('Agent Brad: I called the member: he had already paid.')).toBeNull()
  })

  it('warns on a long single turn even with no labels to point at', () => {
    const long = `Agent Brad: ${'the member explained the position at length. '.repeat(12)}`

    expect(transcriptWarning(long)).toContain('transcript this long')
  })
})
