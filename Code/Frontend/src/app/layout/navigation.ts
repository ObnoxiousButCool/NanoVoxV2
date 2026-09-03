/**
 * The navigation rail's contents.
 *
 * Only screens that exist appear here. A rail entry leading to an empty page
 * would be a worse lie than a short rail.
 *
 * An entry left out of the rail keeps its route and its page — it is hidden, not
 * deleted. The screen stays reachable by typing the address, which is the point:
 * these are operator tools a demo audience should not be clicking into, rather
 * than features being withdrawn.
 *
 * Two ways to leave one out. `hidden` is a decision made in code. `flag` defers
 * to configuration, so the corpus run can be turned on for an operator and off
 * for a demo without a rebuild of anything but the bundle.
 */

import type { AppConfig } from '@/shared/config/env'

/** Configuration a rail entry can be gated on. */
export type NavigationFlag = 'showCorpusRun'

export interface NavigationItem {
  readonly to: string
  readonly label: string
  /** Shown when the rail is collapsed. Kept to one or two characters. */
  readonly glyph: string
  readonly description: string
  /** Omitted from the rail. The route still works. */
  readonly hidden?: boolean
  /** Shown only when this configuration flag is on. The route still works. */
  readonly flag?: NavigationFlag
}

export const NAVIGATION: readonly NavigationItem[] = [
  {
    to: '/overview',
    label: 'Dashboard',
    glyph: '◎',
    description: 'What needs attention, ranked with an owner',
  },
  {
    to: '/calls',
    label: 'Calls',
    glyph: '☰',
    description: 'Every analysed call, most urgent first',
  },
  {
    to: '/brokers',
    label: 'Brokers',
    glyph: '◈',
    description: 'Conduct signals members named aloud',
  },
  {
    to: '/analyze',
    label: 'Analyze new',
    glyph: '+',
    description: 'Paste a transcript and run the five-layer analysis',
  },
  {
    to: '/corpus',
    label: 'Corpus run',
    glyph: '⟳',
    description: 'Re-analyse the whole corpus with live progress',
    flag: 'showCorpusRun',
  },
  {
    to: '/diagnostics',
    label: 'Diagnostics',
    glyph: '◍',
    description: 'Backend and dependency status',
    hidden: true,
  },
]

/**
 * The entries the rail draws, for this configuration.
 *
 * A function rather than a constant: reading configuration at module load would
 * make an unrelated import throw on a misconfigured environment, which is the
 * failure mode `shared/config/env.ts` is written to avoid.
 */
export function visibleNavigation(config: Pick<AppConfig, NavigationFlag>): NavigationItem[] {
  return NAVIGATION.filter((item) => {
    if (item.hidden) {
      return false
    }
    return item.flag ? config[item.flag] : true
  })
}
