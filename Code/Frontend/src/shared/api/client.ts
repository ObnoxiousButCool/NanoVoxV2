/**
 * HTTP client for the NanoVox API.
 *
 * The backend answers every failure with an RFC 9457 problem document carrying a
 * correlation ID. This client preserves that: an `ApiError` keeps the code and
 * the correlation ID so the UI can show something a user can actually quote when
 * reporting a problem, instead of "something went wrong".
 */

import { getConfig } from '@/shared/config/env'

export const CORRELATION_ID_HEADER = 'X-Correlation-ID'

/** RFC 9457 problem document, as returned by the backend. */
export interface ProblemDetail {
  readonly type: string
  readonly title: string
  readonly status: number
  readonly detail: string | null
  readonly code: string
  readonly correlation_id: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly correlationId: string | null
  readonly detail: string | null

  constructor(problem: ProblemDetail) {
    super(problem.title)
    this.name = 'ApiError'
    this.status = problem.status
    this.code = problem.code
    this.correlationId = problem.correlation_id
    this.detail = problem.detail
  }
}

/** A failure before any HTTP response arrived — the backend is unreachable. */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super('The NanoVox API could not be reached.')
    this.name = 'NetworkError'
    this.cause = cause
  }
}

function isProblemDetail(value: unknown): value is ProblemDetail {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as Partial<ProblemDetail>
  return typeof candidate.title === 'string' && typeof candidate.code === 'string'
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    // A non-JSON error body (a proxy error page, for example) is not fatal here;
    // fall through to a synthesised problem below.
  }

  if (isProblemDetail(body)) {
    return new ApiError(body)
  }

  return new ApiError({
    type: 'about:blank',
    title: response.statusText || 'Request failed',
    status: response.status,
    detail: null,
    code: `http_${String(response.status)}`,
    correlation_id: response.headers.get(CORRELATION_ID_HEADER),
  })
}

export interface RequestOptions {
  readonly signal?: AbortSignal
  readonly baseUrl?: string
  readonly fetchFn?: typeof fetch
  /**
   * Non-2xx statuses whose body is still a valid payload rather than an error.
   *
   * `/health` answers 503 when a component is down, but the body is the health
   * report itself — the very thing the diagnostics view needs to display.
   */
  readonly acceptStatuses?: readonly number[]
}

async function request<T>(
  path: string,
  init: RequestInit,
  options: RequestOptions,
): Promise<T> {
  const baseUrl = options.baseUrl ?? getConfig().apiBaseUrl
  const doFetch = options.fetchFn ?? fetch

  let response: Response
  try {
    response = await doFetch(`${baseUrl}${path}`, {
      ...init,
      ...(options.signal ? { signal: options.signal } : {}),
    })
  } catch (cause) {
    throw new NetworkError(cause)
  }

  const accepted = response.ok || (options.acceptStatuses?.includes(response.status) ?? false)
  if (!accepted) {
    throw await toApiError(response)
  }

  return (await response.json()) as T
}

/** Issue a POST with a JSON body. */
export async function postJson<T>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<T> {
  return request<T>(
    path,
    {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    options,
  )
}

/** Issue a DELETE against the API and parse the JSON response. */
export async function deleteJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, { method: 'DELETE', headers: { Accept: 'application/json' } }, options)
}

/** Issue a GET against the API and parse the JSON response. */
export async function getJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, { method: 'GET', headers: { Accept: 'application/json' } }, options)
}
