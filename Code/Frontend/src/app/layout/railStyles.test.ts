/**
 * A guard for a bug jsdom cannot catch.
 *
 * The rail collapse broke silently because `grid-template-columns` was
 * transitioned: with an `fr` unit in the value, Chromium leaves the property
 * stuck at its start value, so the rail stayed 210px wide while the DOM, the
 * stored preference and every unit test all believed it had collapsed.
 *
 * jsdom does no layout, so no rendering test can see this. Reading the
 * stylesheet is the only way to stop it coming back.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

// Resolved from the project root: `import.meta.url` is not a file URL under the
// jsdom transform.
const css = readFileSync(resolve(process.cwd(), 'src/app/layout/AppShell.module.css'), 'utf-8')

describe('rail stylesheet', () => {
  it('defines both the expanded and collapsed column widths', () => {
    expect(css).toContain('grid-template-columns: 210px 1fr')
    expect(css).toContain("[data-collapsed='true']")
    expect(css).toContain('grid-template-columns: 64px 1fr')
  })

  it('never transitions grid-template-columns', () => {
    const transitions = css.match(/transition:[^;]+;/g) ?? []

    for (const declaration of transitions) {
      expect(declaration).not.toContain('grid-template-columns')
      expect(declaration).not.toMatch(/transition:\s*all/)
    }
  })
})
