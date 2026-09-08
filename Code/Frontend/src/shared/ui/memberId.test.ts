import { describe, expect, it } from 'vitest'

import {
  maskIdentifiersInText,
  maskMemberId,
  maskedMemberIdLabel,
} from '@/shared/ui/memberId'

describe('maskMemberId', () => {
  it('shows the last four characters only', () => {
    expect(maskMemberId('CB5519074')).toBe('••••9074')
  })

  it('returns a short identifier whole rather than padding it', () => {
    // '••••CB12' would claim there are characters in front that there are not.
    expect(maskMemberId('CB12')).toBe('CB12')
    expect(maskMemberId('7')).toBe('7')
  })

  it('says the last four aloud, since bullets read as nothing', () => {
    expect(maskedMemberIdLabel('CB5519074')).toBe('Member ending 9074')
    expect(maskedMemberIdLabel('CB12')).toBe('Member CB12')
  })
})

describe('maskIdentifiersInText', () => {
  it('masks a card number a member reads out loud', () => {
    // The opening turn of nearly every call in the corpus.
    expect(maskIdentifiersInText('Why am I paying anything? Member ID CB-8819204.')).toBe(
      'Why am I paying anything? Member ID CB-•••9204.',
    )
  })

  it('masks a carrier subscriber ID, which names the member just as well', () => {
    expect(maskIdentifiersInText('verify you directly with VSP using VS-88410276.')).toBe(
      'verify you directly with VSP using VS-••••0276.',
    )
    expect(maskIdentifiersInText("It's DD-77410398.")).toBe("It's DD-••••0398.")
  })

  it('leaves a group number alone, because it names an employer not a person', () => {
    // And it is the number a broker rings in about, so hiding it would break
    // the screens that exist to answer those calls.
    const line = 'Victor Salinas, HR at Bayside Restaurant Group, group number GRP-402210.'

    expect(maskIdentifiersInText(line)).toBe(line)
  })

  it('preserves length exactly, which the transcript highlighting depends on', () => {
    // A mask that changed the length would slide every highlight after it onto
    // the wrong words.
    const lines = [
      'Member ID CB-8819204.',
      'One says Member ID and one says Subscriber ID.',
      'the plan stops at $1,500 and 50% applies until then',
    ]

    for (const line of lines) {
      expect(maskIdentifiersInText(line)).toHaveLength(line.length)
    }
  })

  it('masks every identifier in a line, not just the first', () => {
    expect(maskIdentifiersInText('CB-8819204 and CB-4471203 are both hers.')).toBe(
      'CB-•••9204 and CB-•••1203 are both hers.',
    )
  })

  it('leaves money, percentages and dates alone', () => {
    const lines = [
      "I'll owe twenty percent — about $340.",
      'The 50% applies until you reach $1,500, then the plan stops.',
      'new enrollments effective the 1st of March 2026',
    ]

    for (const line of lines) {
      expect(maskIdentifiersInText(line)).toBe(line)
    }
  })

  it('leaves a run of digits with no prefix alone', () => {
    // Masking anything numeric would swallow claim totals and call durations.
    expect(maskIdentifiersInText('reference 8819204')).toBe('reference 8819204')
  })
})
