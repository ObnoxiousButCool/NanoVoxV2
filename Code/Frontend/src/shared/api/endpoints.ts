/**
 * Every call the application makes to the backend, in one place.
 *
 * Components use the hooks in `queries.ts`; these functions exist so the URL and
 * the response type are decided once, together.
 */

import { getJson, postJson } from '@/shared/api/client'
import type {
  AgentPerformance,
  Analysis,
  BrokerScorecard,
  CallsPage,
  Health,
  Overview,
  Providers,
  SignalDistribution,
  Taxonomy,
} from '@/shared/api/types'

/** `/health` answers 503 with the report itself when a component is down. */
const HEALTH_ACCEPTED_STATUSES = [503] as const

export interface CallFilters {
  readonly category?: string
  readonly agent?: string
  readonly resolution?: string
  readonly max_score?: number
  readonly min_score?: number
  readonly has_broker_signal?: boolean
  readonly signal?: string
  readonly search?: string
  readonly limit?: number
  readonly offset?: number
}

export interface AnalyzeRequest {
  readonly transcript: string
  readonly provider?: string | null
  readonly model?: string | null
}

function query(filters: CallFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return getJson<Health>('/health', {
    acceptStatuses: HEALTH_ACCEPTED_STATUSES,
    ...(signal ? { signal } : {}),
  })
}

export function fetchProviders(signal?: AbortSignal): Promise<Providers> {
  return getJson<Providers>('/providers', signal ? { signal } : {})
}

export function fetchTaxonomy(signal?: AbortSignal): Promise<Taxonomy> {
  return getJson<Taxonomy>('/taxonomy', signal ? { signal } : {})
}

export function fetchCalls(filters: CallFilters, signal?: AbortSignal): Promise<CallsPage> {
  return getJson<CallsPage>(`/calls${query(filters)}`, signal ? { signal } : {})
}

export function fetchCall(callId: number, signal?: AbortSignal): Promise<Analysis> {
  return getJson<Analysis>(`/calls/${String(callId)}`, signal ? { signal } : {})
}

export function fetchOverview(signal?: AbortSignal): Promise<Overview> {
  return getJson<Overview>('/dashboard/overview', signal ? { signal } : {})
}

export function fetchAgents(signal?: AbortSignal): Promise<AgentPerformance[]> {
  return getJson<AgentPerformance[]>('/dashboard/agents', signal ? { signal } : {})
}

export function fetchBrokers(signal?: AbortSignal): Promise<BrokerScorecard[]> {
  return getJson<BrokerScorecard[]>('/dashboard/brokers', signal ? { signal } : {})
}

export function fetchSignals(signal?: AbortSignal): Promise<SignalDistribution> {
  return getJson<SignalDistribution>('/dashboard/signals', signal ? { signal } : {})
}

export function analyzeTranscript(request: AnalyzeRequest): Promise<Analysis> {
  return postJson<Analysis>('/analyses', request)
}
