import type { HealthReport } from '@/entities/health'
import { getJson } from '@/shared/api/client'

/** 503 carries the health report itself, so it is a valid response here. */
const HEALTH_ACCEPTED_STATUSES = [503] as const

export const healthQueryKey = ['health'] as const

export function fetchHealth(signal?: AbortSignal): Promise<HealthReport> {
  return getJson<HealthReport>('/health', {
    acceptStatuses: HEALTH_ACCEPTED_STATUSES,
    ...(signal ? { signal } : {}),
  })
}
