import { describe, expect, it } from 'vitest'

import { cx } from '@/shared/ui/cx'

describe('cx', () => {
  it('joins the class names it is given', () => {
    expect(cx('badge', 'badgeUp')).toBe('badge badgeUp')
  })

  it('drops absent values rather than emitting "undefined"', () => {
    expect(cx('badge', undefined, null, false, '')).toBe('badge')
  })

  it('returns an empty string when nothing is supplied', () => {
    expect(cx()).toBe('')
  })
})
