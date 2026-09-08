/**
 * Live turn counter for the transcript box.
 *
 * Mirrors the backend parser's rule, and has to: the box says "12 turns
 * detected" before anything is sent, and if the two disagree the count is a
 * lie. Kept small, and covered by tests using the same cases as
 * `tests/unit/test_transcript_parsing.py`.
 *
 * The rule reads a label with different strictness depending on where it sits:
 *
 * * **At the start of a line, almost anything is a speaker** — somebody put it
 *   there. It still has to look like a label, or a wrapped sentence carrying an
 *   early colon becomes a speaker.
 * * **Mid-line, only a recognised role is** — a colon inside speech is
 *   ordinary, so ambiguity resolves toward prose. This is what recovers a
 *   transcript pasted with its line breaks stripped.
 */

const SPEAKER_LINE = /^[^:]{1,40}:/

/** Roles the backend recognises. Mirrors `_MEMBER_WORDS` and `_SYSTEM_WORDS`. */
const ROLE_WORDS = [
  'member',
  'caller',
  'customer',
  'patient',
  'system',
  'ivr',
  'hold',
  'recording',
  'note',
]

/**
 * A recognised role opening a turn from inside a line.
 *
 * Narrower than `ROLE_WORDS`: "note", "hold" and "recording" are things people
 * say mid-sentence. It must follow a closed sentence, because otherwise
 * "I told the member: it was already paid" opens a turn for the member.
 */
const INLINE_LABEL =
  /(?:^|[.!?]["'”’]?\s+)(agent|member|caller|customer|patient|system|ivr)(?:\s+[A-Z][\w'’.-]*){0,2}\s*:\s+/gi

/** A name is short and capitalised; longer than this is a sentence. */
const MOST_WORDS_IN_A_NAME = 3

/** Whether a line's prefix names a speaker rather than ending a clause. */
function looksLikeLabel(speaker: string): boolean {
  const cleaned = speaker.trim()
  if (!cleaned) return false

  const words = cleaned.split(/\s+/)
  const first = (words[0] ?? '').toLowerCase().replace(/[.,]/g, '')
  if (ROLE_WORDS.includes(first) || first.startsWith('agent')) return true

  return (
    words.length <= MOST_WORDS_IN_A_NAME &&
    words.every((word) => word.charAt(0) === word.charAt(0).toUpperCase() && /[A-Za-z]/.test(word))
  )
}

/** How many recognised labels open a turn from inside this line. */
function inlineLabelsIn(text: string): number {
  return text.match(INLINE_LABEL)?.length ?? 0
}

export function countTurns(text: string): number {
  let turns = 0
  let started = false

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    if (!line) {
      continue
    }

    const opens = SPEAKER_LINE.test(line) && looksLikeLabel(line.slice(0, line.indexOf(':')))
    const remainder = opens ? line.slice(line.indexOf(':') + 1) : line

    if (opens) {
      turns += 1
      started = true
    } else if (!started) {
      // Text before any prefix belongs to no turn; the backend ignores it too.
      continue
    }

    // Every recognised label inside the line opens another turn, whether the
    // line opened one of its own or is a continuation of the turn above.
    const inline = inlineLabelsIn(remainder)
    turns += inline
    if (inline > 0) {
      started = true
    }
  }

  return turns
}

/** Whether the text looks like it will parse at all. */
export function hasSpeakerPrefixes(text: string): boolean {
  return countTurns(text) > 0
}

/**
 * Speaker prefixes the parser will read as prose rather than as a speaker.
 *
 * What is left after the parser's own recovery: a bare name mid-line, or a role
 * that does not follow a closed sentence. The parser deliberately does not
 * split on these — guessing wrong misattributes a sentence — so a transcript
 * built that way and pasted flat still collapses, and saying so is the only
 * warning a reader gets.
 */
const UNRECOVERABLE_LABEL = /(?:^|\s)([A-Z][\w'’.-]*(?:\s+[A-Z][\w'’.-]*){0,2})\s*:\s+/g

/** A transcript long enough that one turn is almost certainly a parse failure. */
const LONG_ENOUGH_TO_BE_A_CONVERSATION = 400

/** At least two, so a single incidental colon is not called a fault. */
const ENOUGH_TO_BE_A_PATTERN = 2

export function inlineSpeakerPrefixes(text: string): number {
  let found = 0

  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim()
    // The prefix that opens the line is not a mid-line one, and the ones the
    // parser recovers are not a problem. What remains is what it cannot read.
    const opens = SPEAKER_LINE.test(line) && looksLikeLabel(line.slice(0, line.indexOf(':')))
    const remainder = opens ? line.slice(line.indexOf(':') + 1) : line
    const candidates = remainder.match(UNRECOVERABLE_LABEL)?.length ?? 0
    found += Math.max(candidates - inlineLabelsIn(remainder), 0)
  }

  return found
}

/**
 * Why this transcript will not parse the way it reads, or `null` if it will.
 *
 * Advisory, not a gate. The parser recovers a flattened transcript labelled the
 * way the corpus labels one, so this now fires only on what it cannot reach —
 * chiefly bare names on a single line, where every speaker is scored as the
 * agent and nothing on the screen would otherwise say so.
 */
export function transcriptWarning(text: string): string | null {
  const turns = countTurns(text)
  if (turns === 0) return null // Already reported, and more plainly.

  const stranded = inlineSpeakerPrefixes(text)

  if (turns === 1 && stranded >= ENOUGH_TO_BE_A_PATTERN) {
    return (
      `Only one turn was found, but ${String(stranded)} more speaker labels appear part-way ` +
      'through a line. The parser reads a role — “Caller:”, “Agent Sarah:” — mid-line, but not ' +
      'a bare name, so the whole call will be scored as though one person said all of it.'
    )
  }

  if (turns === 1 && text.trim().length > LONG_ENOUGH_TO_BE_A_CONVERSATION) {
    return (
      'Only one turn was found in a transcript this long. If the line breaks were lost in ' +
      'copying, every speaker will be scored as the first one.'
    )
  }

  if (stranded >= ENOUGH_TO_BE_A_PATTERN) {
    return (
      `${String(stranded)} speaker labels appear part-way through a line and are not a role ` +
      'the parser recognises there. Those turns will be joined to the speaker above.'
    )
  }

  return null
}
