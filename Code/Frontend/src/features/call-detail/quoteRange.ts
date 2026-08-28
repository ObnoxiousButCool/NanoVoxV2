/**
 * Locating a stored quote inside a transcript turn.
 *
 * Separate from the component so it can be tested directly — this is the piece
 * that decides what gets highlighted, and getting it wrong would point evidence
 * at the wrong words.
 */

/** Collapse whitespace and case, exactly as `domain/entities/turn.py` does. */
function normalise(text: string): string {
  return text.replace(/\s+/g, ' ').trim().toLowerCase()
}

/**
 * Locate a quote inside a turn, working in normalised space and mapping the
 * result back onto the original characters so the rendered text is untouched.
 */
export function findQuoteRange(text: string, quote: string): [number, number] | null {
  const needle = normalise(quote)
  if (!needle) {
    return null
  }

  // Index of each original character in its normalised form.
  const positions: number[] = []
  let normalised = ''
  let previousWasSpace = true

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index] ?? ''
    if (/\s/.test(character)) {
      if (!previousWasSpace && normalised.length > 0) {
        positions.push(index)
        normalised += ' '
      }
      previousWasSpace = true
      continue
    }
    positions.push(index)
    normalised += character.toLowerCase()
    previousWasSpace = false
  }

  const trimmed = normalised.trimEnd()
  const start = trimmed.indexOf(needle)
  if (start === -1) {
    return null
  }

  const from = positions[start]
  const to = positions[start + needle.length - 1]
  if (from === undefined || to === undefined) {
    return null
  }
  return [from, to + 1]
}
