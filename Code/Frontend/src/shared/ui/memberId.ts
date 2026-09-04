/**
 * A member identifier, shown as its last four characters only.
 *
 * These identifiers are the one field on these screens that names a real person
 * in another system, and a full one is enough to look somebody up. Four digits
 * is the convention people already read on a card statement: enough to tell two
 * members apart in a list, not enough to be an identifier on its own.
 *
 * **This masks what is drawn, not what is held.** The API still returns the
 * whole identifier, the calls list still filters on it, and it is still in the
 * URL when a link is followed — so this is a courtesy to whoever is looking over
 * the reader's shoulder, not a control that keeps the value from anyone who
 * looks. Making it one means masking in the API and giving the filter a token to
 * use instead, which is a larger change than this file.
 *
 * A short identifier is returned whole rather than padded: `••••CB12` would
 * claim there are characters in front of it that there are not.
 */

const VISIBLE = 4

/** The bullet that stands in for the hidden part. */
const MASK = '•'

export function maskMemberId(memberId: string): string {
  const trimmed = memberId.trim()
  if (trimmed.length <= VISIBLE) return trimmed
  return `${MASK.repeat(VISIBLE)}${trimmed.slice(-VISIBLE)}`
}

/**
 * What a screen reader and a tooltip say for a masked identifier.
 *
 * Bullets are read aloud one by one, or skipped entirely, so the mask alone
 * tells a listener nothing. This says what the four characters are.
 */
export function maskedMemberIdLabel(memberId: string): string {
  const trimmed = memberId.trim()
  if (trimmed.length <= VISIBLE) return `Member ${trimmed}`
  return `Member ending ${trimmed.slice(-VISIBLE)}`
}

/**
 * Identifiers spoken inside a transcript, masked in place.
 *
 * Members read their card number out loud, so the identifier the field masks is
 * also sitting in the second line of nearly every call: *"Why am I paying
 * anything? Member ID CB-8819204."* Masking the field and leaving the transcript
 * alone would be theatre.
 *
 * **The result is the same length as the input, character for character.** That
 * is not incidental: the transcript highlights quoted evidence by index, and a
 * mask that changed the length would slide every highlight after it onto the
 * wrong words. Only the digits become bullets, and only the ones being hidden.
 *
 * Two letters and a run of digits is the shape of a person's identifier in this
 * corpus — a plan member ID, or the subscriber ID a carrier like Delta Dental or
 * VSP knows them by. Group numbers are deliberately left alone: `GRP-402210`
 * names an employer, not a person, and it is the number a broker calls in about,
 * so hiding it would break the screens that exist to answer those calls.
 */

/** Prefixes that identify an organisation rather than a person. */
const GROUP_PREFIXES = new Set(['GRP'])

/** Letters then digits, optionally hyphenated: `CB-8819204`, `VS-88410276`. */
const SPOKEN_IDENTIFIER = /\b([A-Za-z]{2,4})-?(\d{5,12})\b/g

export function maskIdentifiersInText(text: string): string {
  return text.replace(SPOKEN_IDENTIFIER, (whole, prefix: string, digits: string) => {
    if (GROUP_PREFIXES.has(prefix.toUpperCase())) return whole
    if (digits.length <= VISIBLE) return whole
    const lead = whole.slice(0, whole.length - digits.length)
    return `${lead}${MASK.repeat(digits.length - VISIBLE)}${digits.slice(-VISIBLE)}`
  })
}
