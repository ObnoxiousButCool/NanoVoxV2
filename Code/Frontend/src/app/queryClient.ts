import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/shared/api/client'

const MAX_RETRIES = 2
const STALE_TIME_MS = 30_000

/**
 * A 4xx means the request itself was wrong, so repeating it verbatim cannot
 * help. Only transient failures — network errors and 5xx — are worth retrying.
 */
export function shouldRetry(failureCount: number, error: Error): boolean {
  if (failureCount >= MAX_RETRIES) {
    return false
  }
  if (error instanceof ApiError) {
    return error.status >= 500
  }
  return true
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: STALE_TIME_MS,
        refetchOnWindowFocus: false,
      },
    },
  })
}
