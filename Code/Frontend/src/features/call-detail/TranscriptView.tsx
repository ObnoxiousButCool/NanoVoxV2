/**
 * The transcript, with quoted evidence highlighted.
 *
 * Highlighting is driven by the stored turn index plus the stored quote — not by
 * searching the transcript in the browser. A search would highlight the wrong
 * line whenever the same words appear twice, and would silently disagree with
 * the evidence the score was actually computed from.
 *
 * The quote is matched with the same tolerance the backend validator uses:
 * whitespace and case, nothing more. If it does not match, the line is left
 * alone rather than approximated.
 */

import type { ReactNode } from 'react'

import type { Marker, Turn } from '@/shared/api/types'
import { cx } from '@/shared/ui/cx'
import { findQuoteRange } from './quoteRange'
import styles from './CallDetail.module.css'

function highlight(text: string, quotes: readonly string[]): ReactNode {
  const ranges: [number, number][] = []
  for (const quote of quotes) {
    const range = findQuoteRange(text, quote)
    if (range) {
      ranges.push(range)
    }
  }
  if (ranges.length === 0) {
    return text
  }

  // Merge overlapping ranges so two markers quoting the same words produce one
  // highlight rather than nested markup.
  ranges.sort((a, b) => a[0] - b[0])
  const merged: [number, number][] = [ranges[0] as [number, number]]
  for (const [start, end] of ranges.slice(1)) {
    const last = merged[merged.length - 1] as [number, number]
    if (start <= last[1]) {
      last[1] = Math.max(last[1], end)
    } else {
      merged.push([start, end])
    }
  }

  const parts: ReactNode[] = []
  let cursor = 0
  merged.forEach(([start, end], index) => {
    if (start > cursor) {
      parts.push(text.slice(cursor, start))
    }
    parts.push(<mark key={`${String(start)}-${String(index)}`}>{text.slice(start, end)}</mark>)
    cursor = end
  })
  if (cursor < text.length) {
    parts.push(text.slice(cursor))
  }
  return parts
}

export function TranscriptView({
  turns,
  markers,
}: {
  turns: readonly Turn[]
  markers: readonly Marker[]
}) {
  const quotesByTurn = new Map<number, string[]>()
  for (const marker of markers) {
    const existing = quotesByTurn.get(marker.evidence_turn_seq) ?? []
    existing.push(marker.quote)
    quotesByTurn.set(marker.evidence_turn_seq, existing)
  }

  return (
    <div>
      {turns.map((turn) => {
        const quotes = quotesByTurn.get(turn.seq) ?? []
        return (
          <div
            key={turn.seq}
            id={`turn-${String(turn.seq)}`}
            className={cx(
              styles.turn,
              turn.role === 'MEMBER' && styles.member,
              quotes.length > 0 && styles.cited,
            )}
          >
            <span className={styles.who}>{turn.speaker_name ?? turn.role.toLowerCase()}</span>
            <span>{highlight(turn.text, quotes)}</span>
          </div>
        )
      })}
    </div>
  )
}
