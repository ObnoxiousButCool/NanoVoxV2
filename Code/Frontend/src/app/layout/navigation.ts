/**
 * The navigation rail's contents.
 *
 * Only screens that exist appear here. A rail entry leading to an empty page
 * would be a worse lie than a short rail.
 */

export interface NavigationItem {
  readonly to: string
  readonly label: string
  /** Shown when the rail is collapsed. Kept to one or two characters. */
  readonly glyph: string
  readonly description: string
}

export const NAVIGATION: readonly NavigationItem[] = [
  {
    to: '/overview',
    label: 'Overview',
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
  },
  {
    to: '/diagnostics',
    label: 'Diagnostics',
    glyph: '◍',
    description: 'Backend and dependency status',
  },
]
