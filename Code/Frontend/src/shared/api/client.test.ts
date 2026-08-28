import { describe, expect, it, vi } from 'vitest'

import { ApiError, CORRELATION_ID_HEADER, getJson, NetworkError } from '@/shared/api/client'

const BASE_URL = 'http://api.test/api/v1'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('getJson', () => {
  it('returns the parsed body on success', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ status: 'up' }))

    const result = await getJson<{ status: string }>('/health', { baseUrl: BASE_URL, fetchFn })

    expect(result).toEqual({ status: 'up' })
    expect(fetchFn).toHaveBeenCalledWith(`${BASE_URL}/health`, expect.objectContaining({ method: 'GET' }))
  })

  it('preserves the problem document, including the correlation ID', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          type: 'about:blank',
          title: 'Call 4242 does not exist.',
          status: 404,
          detail: null,
          code: 'not_found',
          correlation_id: 'abc123',
        },
        { status: 404 },
      ),
    )

    const error = await getJson('/calls/4242', { baseUrl: BASE_URL, fetchFn }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.status).toBe(404)
    expect(apiError.code).toBe('not_found')
    expect(apiError.correlationId).toBe('abc123')
    expect(apiError.message).toBe('Call 4242 does not exist.')
  })

  it('synthesises an error when the body is not a problem document', async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      new Response('<html>Gateway timeout</html>', {
        status: 504,
        statusText: 'Gateway Timeout',
        headers: { [CORRELATION_ID_HEADER]: 'from-header' },
      }),
    )

    const error = (await getJson('/health', { baseUrl: BASE_URL, fetchFn }).catch(
      (caught: unknown) => caught,
    )) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(504)
    expect(error.code).toBe('http_504')
    expect(error.correlationId).toBe('from-header')
  })

  it('reports an unreachable backend as a NetworkError', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))

    const error = await getJson('/health', { baseUrl: BASE_URL, fetchFn }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(NetworkError)
  })

  it('treats an accepted non-2xx status as a valid payload', async () => {
    // /health answers 503 with the health report itself.
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ status: 'down' }, { status: 503 }))

    const result = await getJson<{ status: string }>('/health', {
      baseUrl: BASE_URL,
      fetchFn,
      acceptStatuses: [503],
    })

    expect(result).toEqual({ status: 'down' })
  })

  it('still rejects statuses that were not accepted', async () => {
    const fetchFn = vi.fn().mockResolvedValue(jsonResponse({ status: 'down' }, { status: 500 }))

    await expect(
      getJson('/health', { baseUrl: BASE_URL, fetchFn, acceptStatuses: [503] }),
    ).rejects.toBeInstanceOf(ApiError)
  })
})
