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
