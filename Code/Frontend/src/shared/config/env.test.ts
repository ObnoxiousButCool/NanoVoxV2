import { afterEach, describe, expect, it } from 'vitest'

import { getConfig, readConfig, resetConfigCache } from '@/shared/config/env'

afterEach(() => {
  resetConfigCache()
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
