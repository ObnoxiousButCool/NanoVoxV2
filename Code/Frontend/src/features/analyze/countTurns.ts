/**
 * Live turn counter for the transcript box.
 *
 * Mirrors the backend parser's rule: a line beginning with a short
 * `Speaker:` prefix starts a turn, and anything else continues the one above.
 * The count is advisory — the backend is authoritative — but it has to agree,
 * or the box will say "12 turns detected" and the analysis will disagree.
 *
 * Kept deliberately small and covered by tests that use the same corpus extract
 * as the backend's parser tests.
 */

const SPEAKER_LINE = /^[^:]{1,40}:/

export function countTurns(text: string): number {
  let turns = 0
  let started = false

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) {
      continue
    }
    if (SPEAKER_LINE.test(line)) {
      turns += 1
      started = true
    } else if (!started) {
      // Text before any prefix belongs to no turn; the backend ignores it too.
      continue
    }
  }

  return turns
}

/** Whether the text looks like it will parse at all. */
export function hasSpeakerPrefixes(text: string): boolean {
  return countTurns(text) > 0
}
