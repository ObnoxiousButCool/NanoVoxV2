/**
 * Every call the application makes to the backend, in one place.
 *
 * Components use the hooks in `queries.ts`; these functions exist so the URL and
 * the response type are decided once, together.
 */

import { deleteJson, getJson, postJson } from '@/shared/api/client'
import { getConfig } from '@/shared/config/env'
import type {
  AgentPerformance,
  Analysis,
  BrokerScorecard,
  CallsPage,
  CorpusRun,
  CorpusRunSummary,
  CorpusStatus,
  Effort,
  Health,
  MembersAtRisk,
  Overview,
  Providers,
  Pulse,
  ResolutionTime,
  TimeValue,
  SignalDistribution,
  Taxonomy,
  WorkMix,
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
  readonly broker?: string
  readonly signal?: string
  /**
   * An L4 finding category code.
   *
   * The finding taxonomy, not `category` above: a Coverage & Benefits call can
   * raise a Process Breakdown finding, so the two narrow the list differently.
   * This is how an inference opens the calls it counted.
   */
  readonly l4_category?: string
  /** Who called: MEMBER, EMPLOYER or BROKER. */
  readonly caller?: string
  /** Member identifier, as stated in the call. */
  readonly member?: string
  readonly search?: string
  readonly limit?: number
  readonly offset?: number
  readonly sort?: CallSortKey
  readonly direction?: 'asc' | 'desc'
}

/** Columns the API will order the calls list by. */
export const CALL_SORTS = [
  'severity',
  'reference',
  'category',
  'agent',
  'resolution',
  'score',
  'analysed_at',
] as const
export type CallSortKey = (typeof CALL_SORTS)[number]

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

export function fetchEffort(signal?: AbortSignal): Promise<Effort> {
  return getJson<Effort>('/dashboard/effort', signal ? { signal } : {})
}

export function fetchResolutionTime(signal?: AbortSignal): Promise<ResolutionTime> {
  return getJson<ResolutionTime>('/dashboard/resolution-time', signal ? { signal } : {})
}

export function fetchTimeValue(signal?: AbortSignal): Promise<TimeValue> {
  return getJson<TimeValue>('/dashboard/time-value', signal ? { signal } : {})
}

export function fetchMembersAtRisk(signal?: AbortSignal): Promise<MembersAtRisk> {
  return getJson<MembersAtRisk>('/dashboard/members-at-risk', signal ? { signal } : {})
}

export function fetchPulse(signal?: AbortSignal): Promise<Pulse> {
  return getJson<Pulse>('/dashboard/pulse', signal ? { signal } : {})
}

export function fetchWorkMix(signal?: AbortSignal): Promise<WorkMix> {
  return getJson<WorkMix>('/dashboard/work-mix', signal ? { signal } : {})
}

export function fetchSignals(signal?: AbortSignal): Promise<SignalDistribution> {
  return getJson<SignalDistribution>('/dashboard/signals', signal ? { signal } : {})
}

export function analyzeTranscript(request: AnalyzeRequest): Promise<Analysis> {
  return postJson<Analysis>('/analyses', request)
}

export interface StartRunRequest {
  readonly provider?: string | null
  readonly model?: string | null
  readonly force?: boolean
  /** Required by the API for a provider that charges per token. */
  readonly acknowledge_cost?: boolean
}

export function fetchCorpusStatus(signal?: AbortSignal): Promise<CorpusStatus> {
  return getJson<CorpusStatus>('/corpus', signal ? { signal } : {})
}

export function fetchRuns(signal?: AbortSignal): Promise<CorpusRunSummary[]> {
  return getJson<CorpusRunSummary[]>('/corpus/runs', signal ? { signal } : {})
}

export function fetchRun(runId: number, signal?: AbortSignal): Promise<CorpusRun> {
  return getJson<CorpusRun>(`/corpus/runs/${String(runId)}`, signal ? { signal } : {})
}

export function startRun(request: StartRunRequest): Promise<CorpusRun> {
  return postJson<CorpusRun>('/corpus/runs', request)
}

export function cancelRun(runId: number): Promise<CorpusRun> {
  return postJson<CorpusRun>(`/corpus/runs/${String(runId)}/cancel`, {})
}

export function resumeRun(runId: number): Promise<CorpusRun> {
  return postJson<CorpusRun>(`/corpus/runs/${String(runId)}/resume`, {})
}

export interface ClearedCorpus {
  readonly calls: number
  readonly runs: number
  readonly ground_truth_kept: boolean
}

/** Discard every analysed call. Ground truth is kept; the API refuses with 409
 *  while a run is working. */
export function clearCorpus(): Promise<ClearedCorpus> {
  return deleteJson<ClearedCorpus>('/corpus/analyses')
}

/** The run's progress stream, for `EventSource`. Relative when the API is
 *  served from this origin; EventSource resolves it against the page. */
export function runStreamUrl(runId: number): string {
  return `${getConfig().apiBaseUrl}/corpus/runs/${String(runId)}/stream`
}
