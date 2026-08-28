import { useQuery } from '@tanstack/react-query'

import type { HealthReport } from '@/entities/health'
import { fetchHealth, healthQueryKey } from '@/features/diagnostics/api'

const REFETCH_INTERVAL_MS = 30_000

export function useHealth() {
  return useQuery<HealthReport>({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: REFETCH_INTERVAL_MS,
  })
}
