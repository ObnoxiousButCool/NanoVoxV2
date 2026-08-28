/**
 * Rail collapse state, remembered between visits.
 *
 * Persisted so someone who works collapsed does not have to re-collapse on every
 * load. Below the prototype's 1080px breakpoint the rail collapses on its own,
 * and the stored preference is deliberately not overwritten — widening the
 * window restores whatever the user last chose.
 */

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'nanovox.rail.collapsed'
export const NARROW_BREAKPOINT_PX = 1080

const NARROW_QUERY = `(max-width: ${String(NARROW_BREAKPOINT_PX)}px)`

/**
 * `matchMedia` is typed as always present but is absent in jsdom, so the check
 * is real even though TypeScript believes otherwise.
 */
function matchNarrow(): MediaQueryList | null {
  const media = (globalThis as { matchMedia?: (query: string) => MediaQueryList }).matchMedia
  return typeof media === 'function' ? media.call(globalThis, NARROW_QUERY) : null
}

function readStored(): boolean {
  try {
    return globalThis.localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    // Private windows and blocked site data both throw; the rail still works.
    return false
  }
}

function write(collapsed: boolean): void {
  try {
    globalThis.localStorage.setItem(STORAGE_KEY, String(collapsed))
  } catch {
    // Losing the preference is not worth failing a render over.
  }
}

export interface CollapsibleRail {
  readonly collapsed: boolean
  readonly toggle: () => void
  /** True when the viewport, not the user, is forcing the collapse. */
  readonly forcedByViewport: boolean
}

export function useCollapsibleRail(): CollapsibleRail {
  const [preferred, setPreferred] = useState(readStored)
  const [narrow, setNarrow] = useState(() => matchNarrow()?.matches ?? false)

  useEffect(() => {
    const query = matchNarrow()
    if (!query) {
      return
    }
    const onChange = (event: MediaQueryListEvent) => {
      setNarrow(event.matches)
    }
    query.addEventListener('change', onChange)
    return () => {
      query.removeEventListener('change', onChange)
    }
  }, [])

  const toggle = useCallback(() => {
    setPreferred((current) => {
      const next = !current
      write(next)
      return next
    })
  }, [])

  return { collapsed: preferred || narrow, toggle, forcedByViewport: narrow && !preferred }
}
