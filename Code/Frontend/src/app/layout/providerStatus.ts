/**
 * Whether the rail shows a status block, and what it says.
 *
 * Two switches, because they hide different amounts:
 *
 * * `SHOW_RAIL_STATUS` — the whole block, dot and text. Off, the rail is
 *   navigation only.
 * * `SHOW_PROVIDER_STATUS` — just the line naming the provider and where
 *   transcripts go. Only consulted when the block is shown at all.
 *
 * Both are hidden rather than removed: the wiring stays, the wording stays
 * tested, and either is one line to bring back.
 *
 * Kept out of the component file so it can be imported and tested on its own —
 * and because a component file that also exports helpers breaks Fast Refresh.
 */

/** The rail's health dot and status text. Set true to show it again. */
export const SHOW_RAIL_STATUS: boolean = false

import type { Providers } from '@/shared/api/types'

/**
 * Whether the rail states which provider is in use.
 *
 * Hidden, not removed: the wiring behind it stays, and the statement is still
 * correct — it is simply not on screen. Set this to true to show it again.
 *
 * The reason to hide it at all is that the claim is only worth making when
 * somebody is in a position to act on it. What must never happen is the
 * opposite: showing a *reassuring* claim that is untrue, which is what this
 * replaced.
 */
export const SHOW_PROVIDER_STATUS: boolean = false

/**
 * What the rail says about where transcripts go.
 *
 * This is a privacy claim about member health conversations, so it is derived
 * from the configured provider rather than written into the page. It previously
 * read "Nothing leaves this environment" unconditionally, which was false for
 * every cloud provider and most misleading exactly when it mattered.
 *
 * While the provider is unknown — still loading, or the call failed — it claims
 * nothing. A guarantee that has not been verified must not be displayed.
 */
export function providerStatus(
  providers: Providers | undefined,
): { headline: string; detail: string } {
  const active = providers?.providers.find((entry) => entry.name === providers.default)
  if (!active) {
    return { headline: 'Checking provider…', detail: 'Where transcripts go is not yet known' }
  }
  if (active.local) {
    return {
      headline: `${active.name} · on-prem`,
      detail: 'Transcripts stay in this environment',
    }
  }
  return {
    headline: `${active.name} · cloud`,
    detail: `Transcripts are sent to ${active.name}`,
  }
}
