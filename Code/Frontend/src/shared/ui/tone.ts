/**
 * Mapping API vocabularies onto the prototype's colour language.
 *
 * Separate from the components so the module exports only components, which is
 * what keeps fast refresh working.
 */

export type Tone = 'neutral' | 'high' | 'medium' | 'low' | 'broker'

/** Severity from the API onto a tone. */
export function toneForSeverity(severity: string): Tone {
  if (severity === 'CRITICAL' || severity === 'HIGH') {
    return 'high'
  }
  if (severity === 'MEDIUM') {
    return 'medium'
  }
  return 'low'
}

/** Call outcome onto a tone: unresolved reads as urgent. */
export function toneForResolution(resolution: string): Tone {
  if (resolution === 'UNRESOLVED') {
    return 'high'
  }
  if (resolution === 'RESOLVED') {
    return 'low'
  }
  return 'medium'
}
