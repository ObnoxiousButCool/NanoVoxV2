/**
 * Which panels a reader has collapsed, remembered between visits.
 *
 * Someone reviewing calls tends to care about the same one or two layers all
 * afternoon. Re-collapsing the other three on every call is the kind of small
 * friction that stops a screen being used, so the choice is stored.
 *
 * Panels start expanded. A collapsed default would hide the analysis behind a
 * click on first sight, and the point of the page is that the evidence is there
 * to read.
 */

import { useCallback, useState } from 'react'

function read(storageKey: string): ReadonlySet<string> {
  try {
    const stored = globalThis.localStorage.getItem(storageKey)
    if (!stored) {
      return new Set()
    }
    const parsed: unknown = JSON.parse(stored)
    return new Set(Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : [])
  } catch {
    // Private windows, blocked site data and anything hand-edited all land
    // here. Losing the preference is not worth failing a render over.
    return new Set()
  }
}

function write(storageKey: string, collapsed: ReadonlySet<string>): void {
  try {
    globalThis.localStorage.setItem(storageKey, JSON.stringify([...collapsed]))
  } catch {
    // As above: the panels still work, they just forget.
  }
}

export interface CollapsedPanels {
  readonly isCollapsed: (id: string) => boolean
  readonly toggle: (id: string) => void
}

export function useCollapsedPanels(storageKey: string): CollapsedPanels {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => read(storageKey))

  const toggle = useCallback(
    (id: string) => {
      setCollapsed((current) => {
        const next = new Set(current)
        if (!next.delete(id)) {
          next.add(id)
        }
        write(storageKey, next)
        return next
      })
    },
    [storageKey],
  )

  const isCollapsed = useCallback((id: string) => collapsed.has(id), [collapsed])

  return { isCollapsed, toggle }
}
