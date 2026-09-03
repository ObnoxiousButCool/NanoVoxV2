/**
 * The navigation rail's contents.
 *
 * Only screens that exist appear here. A rail entry leading to an empty page
 * would be a worse lie than a short rail.
 *
 * An entry marked `hidden` keeps its route and its page — it is left out of the
 * rail, not deleted. The screen is still reachable by typing the address, which
 * is the point: these are operator tools that a demo audience should not be
 * clicking into, rather than features being withdrawn. Flip the flag to bring
 * one back.
 */

export interface NavigationItem {
  readonly to: string
  readonly label: string
  /** Shown when the rail is collapsed. Kept to one or two characters. */
  readonly glyph: string
  readonly description: string
  /** Omitted from the rail. The route still works. */
  readonly hidden?: boolean
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
    hidden: true,
  },
  {
    to: '/diagnostics',
    label: 'Diagnostics',
    glyph: '◍',
    description: 'Backend and dependency status',
    hidden: true,
  },
]

/** The entries the rail draws. Hidden ones keep their routes. */
export const VISIBLE_NAVIGATION: readonly NavigationItem[] = NAVIGATION.filter(
  (item) => !item.hidden,
)
