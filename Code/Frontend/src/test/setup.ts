import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom does not implement this at all — every call logs "Not implemented"
// to stderr instead of silently no-op'ing. A no-op here is correct: nothing
// under test relies on the browser's own scroll position changing, only on
// this having been *called*, which individual tests can still spy on.
window.scrollTo = () => {}

afterEach(() => {
  cleanup()
})
