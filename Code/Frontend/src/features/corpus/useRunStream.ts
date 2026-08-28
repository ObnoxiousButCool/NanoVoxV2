/**
 * Live progress for one corpus run, over Server-Sent Events.
 *
 * The run record, not this stream, is the source of truth. Every event carries a
 * full progress snapshot rather than a delta, so a dropped connection, a
 * backgrounded tab or a browser that missed ten events costs nothing: the next
 * event it receives is complete, and the stream opens with a snapshot for
 * exactly that reason.
 *
 * `EventSource` reconnects on its own, which is what we want during a run that
 * lasts hours. It is closed here as soon as the run finishes so a completed run
 * does not hold a socket open forever.
 */

import { useEffect, useRef, useState } from 'react'

import { runStreamUrl } from '@/shared/api/endpoints'
import type { CorpusRunItem, RunProgress } from '@/shared/api/types'

export const RUN_EVENT_KINDS = [
  'snapshot',
  'item_started',
  'item_finished',
  'run_finished',
] as const

export type RunEventKind = (typeof RUN_EVENT_KINDS)[number]

export interface RunEvent {
  readonly run_id: number
  readonly kind: RunEventKind
  readonly at: string
  readonly run_status: string
  readonly message: string
  readonly progress: RunProgress
  readonly item: CorpusRunItem | null
}

export interface RunStream {
  /** The most recent event, or null before the first one arrives. */
  readonly latest: RunEvent | null
  /** Calls finished during this connection, most recent first. */
  readonly recent: readonly CorpusRunItem[]
  readonly connected: boolean
  /** True once the run reported that it had finished. */
  readonly done: boolean
}

const EMPTY: RunStream = { latest: null, recent: [], connected: false, done: false }

/** How many finished calls to keep on screen. */
export const RECENT_LIMIT = 8

function isRunEvent(value: unknown): value is RunEvent {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as Partial<RunEvent>
  return typeof candidate.kind === 'string' && typeof candidate.run_status === 'string'
}

/**
 * Watch a run. Pass `null` to watch nothing — a finished run needs no socket.
 */
export function useRunStream(runId: number | null): RunStream {
  const [state, setState] = useState<RunStream>(EMPTY)
  // Kept in a ref so the effect does not restart, and reconnect, on every event.
  const source = useRef<EventSource | null>(null)

  useEffect(() => {
    setState(EMPTY)
    if (runId === null) {
      return
    }

    const stream = new EventSource(runStreamUrl(runId))
    source.current = stream

    stream.onopen = () => {
      setState((current) => ({ ...current, connected: true }))
    }

    stream.onerror = () => {
      // Not surfaced as a failure: EventSource retries by itself, and a run that
      // takes hours will drop a connection at some point without anything being
      // wrong. The run record is what a reader falls back to.
      setState((current) => ({ ...current, connected: false }))
    }

    // The backend names every frame (`event: item_finished`), and `onmessage`
    // fires only for unnamed ones — so each kind is registered explicitly.
    // Keep-alive frames are SSE comments and EventSource discards them for us.
    const handle = (message: MessageEvent<string>) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(message.data)
      } catch {
        return
      }
      if (!isRunEvent(parsed)) {
        return
      }

      const event = parsed
      setState((current) => ({
        latest: event,
        recent: nextRecent(current.recent, event),
        connected: true,
        done: current.done || event.kind === 'run_finished',
      }))

      if (event.kind === 'run_finished') {
        stream.close()
      }
    }

    for (const kind of RUN_EVENT_KINDS) {
      stream.addEventListener(kind, handle as EventListener)
    }

    return () => {
      for (const kind of RUN_EVENT_KINDS) {
        stream.removeEventListener(kind, handle as EventListener)
      }
      stream.close()
      source.current = null
    }
  }, [runId])

  return state
}

function nextRecent(
  recent: readonly CorpusRunItem[],
  event: RunEvent,
): readonly CorpusRunItem[] {
  if (event.kind !== 'item_finished' || event.item === null) {
    return recent
  }
  const item = event.item
  const others = recent.filter((entry) => entry.source_id !== item.source_id)
  return [item, ...others].slice(0, RECENT_LIMIT)
}
