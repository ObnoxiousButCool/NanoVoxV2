import { describe, expect, it } from 'vitest'

import { createQueryClient, shouldRetry } from '@/app/queryClient'
import { ApiError, NetworkError } from '@/shared/api/client'

function apiError(status: number): ApiError {
  return new ApiError({
    type: 'about:blank',
    title: 'failed',
    status,
    detail: null,
    code: `http_${String(status)}`,
    correlation_id: null,
  })
}

describe('shouldRetry', () => {
  it('does not retry a client error — the request itself was wrong', () => {
    expect(shouldRetry(0, apiError(404))).toBe(false)
    expect(shouldRetry(0, apiError(422))).toBe(false)
  })

  it('retries a server error', () => {
    expect(shouldRetry(0, apiError(503))).toBe(true)
  })

  it('retries an unreachable backend', () => {
    expect(shouldRetry(0, new NetworkError(new TypeError('Failed to fetch')))).toBe(true)
  })

  it('gives up after the retry limit', () => {
    expect(shouldRetry(2, apiError(503))).toBe(false)
  })
})

describe('createQueryClient', () => {
  it('applies the shared query defaults', () => {
    const defaults = createQueryClient().getDefaultOptions().queries

    expect(defaults?.retry).toBe(shouldRetry)
    expect(defaults?.staleTime).toBe(30_000)
    expect(defaults?.refetchOnWindowFocus).toBe(false)
  })
})
