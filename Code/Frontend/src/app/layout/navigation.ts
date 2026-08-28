/**
 * The navigation rail's contents.
 *
 * Only screens that exist appear here. A rail entry leading to an empty page
 * would be a worse lie than a short rail — the Overview, Calls and Brokers
 * screens arrive in P6 and will be added then.
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
    to: '/analyze',
    label: 'Analyze new',
    glyph: '+',
    description: 'Paste a transcript and run the five-layer analysis',
  },
  {
    to: '/diagnostics',
    label: 'Diagnostics',
    glyph: '◍',
    description: 'Backend and dependency status',
  },
]
