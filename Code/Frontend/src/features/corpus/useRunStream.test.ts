import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RECENT_LIMIT, useRunStream, type RunEvent } from '@/features/corpus/useRunStream'

/**
 * jsdom has no EventSource, so one is stood up here.
 *
 * It is deliberately faithful about the thing that broke in the real client:
 * frames are *named* events, so a listener registered for "message" alone
 * receives nothing.
 */
class FakeEventSource {
  static instances: FakeEventSource[] = []

  readonly url: string
  readonly listeners = new Map<string, Set<(event: MessageEvent<string>) => void>>()
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(kind: string, handler: (event: MessageEvent<string>) => void): void {
    const existing = this.listeners.get(kind) ?? new Set()
    existing.add(handler)
    this.listeners.set(kind, existing)
  }

  removeEventListener(kind: string, handler: (event: MessageEvent<string>) => void): void {
    this.listeners.get(kind)?.delete(handler)
  }

  close(): void {
    this.closed = true
  }

  /** Deliver a named frame, as the backend sends it. */
  emit(event: Partial<RunEvent> & { kind: string }): void {
    const payload = {
      run_id: 1,
      at: '2026-08-28T12:00:00Z',
      run_status: 'RUNNING',
      message: '',
      progress: progress(),
      item: null,
      ...event,
    }
    const message = { data: JSON.stringify(payload) } as MessageEvent<string>
    for (const handler of this.listeners.get(event.kind) ?? []) {
      handler(message)
    }
  }

  emitRaw(kind: string, data: string): void {
    for (const handler of this.listeners.get(kind) ?? []) {
      handler({ data } as MessageEvent<string>)
    }
  }
}

function progress(completed = 0) {
  return {
    total: 3,
    completed,
    failed: 0,
    skipped: 0,
    cancelled: 0,
    running: 1,
    pending: 3 - completed - 1,
    finished: completed,
    remaining: 3 - completed,
    percent_complete: (completed / 3) * 100,
  }
}

function item(sourceId: string, callId = 1) {
  return {
    source_id: sourceId,
    reference: sourceId.replace('call_', 'C'),
    title: 'Fixture call',
    status: 'COMPLETED',
    call_id: callId,
    message: '',
    started_at: null,
    finished_at: null,
    duration_ms: 1200,
  }
}

function current(): FakeEventSource {
  const source = FakeEventSource.instances.at(-1)
  if (!source) {
    throw new Error('No EventSource was opened.')
  }
  return source
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useRunStream', () => {
  it('opens no connection when there is nothing to watch', () => {
    renderHook(() => useRunStream(null))

    expect(FakeEventSource.instances).toHaveLength(0)
  })

  it('subscribes to the run it is given', () => {
    renderHook(() => useRunStream(7))

    expect(current().url).toContain('/corpus/runs/7/stream')
  })

  it('receives named frames, which is how the backend sends them', () => {
    // A client listening only for unnamed "message" events would sit silent
    // through an entire run.
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emit({ kind: 'snapshot' })
    })

    expect(result.current.latest?.kind).toBe('snapshot')
  })

  it('takes progress from the event rather than counting locally', () => {
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emit({ kind: 'item_finished', progress: progress(2), item: item('call_002') })
    })

    expect(result.current.latest?.progress.completed).toBe(2)
  })

  it('keeps finished calls, most recent first', () => {
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emit({ kind: 'item_finished', item: item('call_001') })
      current().emit({ kind: 'item_finished', item: item('call_002') })
    })

    expect(result.current.recent.map((entry) => entry.source_id)).toEqual([
      'call_002',
      'call_001',
    ])
  })

  it('does not list the same call twice when an event repeats', () => {
    // A reconnect replays nothing, but a retry of one call can finish twice.
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emit({ kind: 'item_finished', item: item('call_001') })
      current().emit({ kind: 'item_finished', item: item('call_001') })
    })

    expect(result.current.recent).toHaveLength(1)
  })

  it('keeps the list short enough to read', () => {
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      for (let index = 0; index < RECENT_LIMIT + 5; index += 1) {
        current().emit({ kind: 'item_finished', item: item(`call_${String(index)}`) })
      }
    })

    expect(result.current.recent).toHaveLength(RECENT_LIMIT)
  })

  it('closes the socket when the run finishes', () => {
    // A completed run holding a connection open forever is a leak.
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emit({ kind: 'run_finished', run_status: 'COMPLETED' })
    })

    expect(result.current.done).toBe(true)
    expect(current().closed).toBe(true)
  })

  it('reports a dropped connection without calling it a failure', async () => {
    // EventSource reconnects by itself, and a run lasting hours will drop at
    // some point with nothing actually wrong.
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().onopen?.()
    })
    await waitFor(() => {
      expect(result.current.connected).toBe(true)
    })

    act(() => {
      current().onerror?.()
    })

    expect(result.current.connected).toBe(false)
    expect(result.current.done).toBe(false)
  })

  it('ignores a frame that is not valid JSON', () => {
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emitRaw('snapshot', 'not json')
    })

    expect(result.current.latest).toBeNull()
  })

  it('ignores a frame that is not a run event', () => {
    const { result } = renderHook(() => useRunStream(1))

    act(() => {
      current().emitRaw('snapshot', '{"unexpected":true}')
    })

    expect(result.current.latest).toBeNull()
  })

  it('closes the old connection when the watched run changes', () => {
    const { rerender } = renderHook(({ runId }) => useRunStream(runId), {
      initialProps: { runId: 1 },
    })
    const first = current()

    rerender({ runId: 2 })

    expect(first.closed).toBe(true)
    expect(current().url).toContain('/corpus/runs/2/stream')
  })

  it('closes the connection when the screen goes away', () => {
    const { unmount } = renderHook(() => useRunStream(1))
    const source = current()

    unmount()

    expect(source.closed).toBe(true)
  })
})
