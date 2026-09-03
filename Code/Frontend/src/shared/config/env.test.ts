import { afterEach, describe, expect, it } from 'vitest'

import { getConfig, readConfig, resetConfigCache } from '@/shared/config/env'

afterEach(() => {
  resetConfigCache()
})

describe('readConfig — feature flags', () => {
  const BASE = {
    VITE_API_BASE_URL: 'http://localhost:8000/api/v1',
    VITE_APP_NAME: 'NanoVox',
  }

  it('shows the corpus run when nothing says otherwise', () => {
    // The screen exists; hiding it is the deliberate act, not showing it.
    expect(readConfig(BASE).showCorpusRun).toBe(true)
  })

  it.each(['true', 'TRUE', '1', 'yes', 'on'])('reads %s as on', (value) => {
    expect(readConfig({ ...BASE, VITE_SHOW_CORPUS_RUN: value }).showCorpusRun).toBe(true)
  })

  it.each(['false', 'False', '0', 'no', 'off'])('reads %s as off', (value) => {
    expect(readConfig({ ...BASE, VITE_SHOW_CORPUS_RUN: value }).showCorpusRun).toBe(false)
  })

  it('treats blank as unset rather than as off', () => {
    expect(readConfig({ ...BASE, VITE_SHOW_CORPUS_RUN: '   ' }).showCorpusRun).toBe(true)
  })

  it('refuses a value it cannot read rather than assuming off', () => {
    // `flase` quietly hiding a screen is the misconfiguration this catches.
    expect(() => readConfig({ ...BASE, VITE_SHOW_CORPUS_RUN: 'flase' })).toThrow(
      /VITE_SHOW_CORPUS_RUN must be true or false/,
    )
  })
})

describe('readConfig', () => {
  it('reads a complete configuration', () => {
    const config = readConfig({
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1',
      VITE_APP_NAME: 'NanoVox',
    })

    expect(config.apiBaseUrl).toBe('http://localhost:8000/api/v1')
    expect(config.appName).toBe('NanoVox')
  })

  it('strips a trailing slash so paths do not double up', () => {
    const config = readConfig({
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1///',
      VITE_APP_NAME: 'NanoVox',
    })

    expect(config.apiBaseUrl).toBe('http://localhost:8000/api/v1')
  })

  it('names the missing variable rather than failing later', () => {
    expect(() => readConfig({ VITE_APP_NAME: 'NanoVox' })).toThrow(/VITE_API_BASE_URL is not set/)
  })

  it('rejects a blank variable the same as a missing one', () => {
    expect(() =>
      readConfig({ VITE_API_BASE_URL: '   ', VITE_APP_NAME: 'NanoVox' }),
    ).toThrow(/VITE_API_BASE_URL is not set/)
  })

  it('rejects a malformed URL', () => {
    expect(() =>
      readConfig({ VITE_API_BASE_URL: 'not-a-url', VITE_APP_NAME: 'NanoVox' }),
    ).toThrow(/must be an absolute URL or a root-relative path/)
  })

  it('accepts a root-relative path', () => {
    // The deployed form: the API is served by the same origin as this bundle,
    // so one build works on any host.
    expect(
      readConfig({ VITE_API_BASE_URL: '/api/v1', VITE_APP_NAME: 'NanoVox' }).apiBaseUrl,
    ).toBe('/api/v1')
  })

  it('strips a trailing slash from a relative path too', () => {
    expect(
      readConfig({ VITE_API_BASE_URL: '/api/v1/', VITE_APP_NAME: 'NanoVox' }).apiBaseUrl,
    ).toBe('/api/v1')
  })
})

describe('getConfig', () => {
  it('reads the configuration from the environment', () => {
    expect(getConfig().apiBaseUrl).toBe('http://api.test/api/v1')
  })

  it('resolves once and reuses the result', () => {
    expect(getConfig()).toBe(getConfig())
  })

  it('re-reads after the cache is cleared', () => {
    const first = getConfig()
    resetConfigCache()

    expect(getConfig()).not.toBe(first)
    expect(getConfig()).toEqual(first)
  })
})
