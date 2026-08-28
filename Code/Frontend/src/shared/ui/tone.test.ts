import { describe, expect, it } from 'vitest'

import { toneForResolution, toneForSeverity } from '@/shared/ui/tone'

describe('toneForSeverity', () => {
  it('gives critical and high the same urgent colour', () => {
    // The queue is already ordered; the colour marks "act", not the rank.
    expect(toneForSeverity('CRITICAL')).toBe('high')
    expect(toneForSeverity('HIGH')).toBe('high')
  })

  it('separates medium from the rest', () => {
    expect(toneForSeverity('MEDIUM')).toBe('medium')
    expect(toneForSeverity('LOW')).toBe('low')
  })

  it('falls back to the calm colour for a severity it does not know', () => {
    // A new severity must not silently render as an emergency.
    expect(toneForSeverity('INFORMATIONAL')).toBe('low')
  })
})

describe('toneForResolution', () => {
  it('reads unresolved as urgent and resolved as settled', () => {
    expect(toneForResolution('UNRESOLVED')).toBe('high')
    expect(toneForResolution('RESOLVED')).toBe('low')
  })

  it('treats a partial outcome as neither settled nor urgent', () => {
    expect(toneForResolution('PARTIALLY_RESOLVED')).toBe('medium')
    expect(toneForResolution('ESCALATED')).toBe('medium')
  })

  it('does not colour an unknown outcome as resolved', () => {
    // Mistaking an unknown outcome for "done" is the dangerous direction.
    expect(toneForResolution('SOMETHING_NEW')).toBe('medium')
  })
})
