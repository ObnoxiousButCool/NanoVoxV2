/**
 * React Query hooks.
 *
 * Query keys are declared once here so an invalidation cannot miss a consumer:
 * analysing a call must refresh the calls list and every dashboard figure, since
 * all of them are counted from the same stored calls.
 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  analyzeTranscript,
  cancelRun,
  clearCorpus,
  fetchAgents,
  fetchBrokers,
  fetchCall,
  fetchCalls,
  fetchCorpusImports,
  fetchCorpusStatus,
  fetchHealth,
  importCorpusDocument,
  fetchOverview,
  fetchProviders,
  fetchRun,
  fetchRuns,
  fetchEffort,
  fetchMembersAtRisk,
  fetchResolutionTime,
  fetchTimeValue,
  fetchPulse,
  fetchWorkMix,
  fetchSignals,
  fetchTaxonomy,
  resumeRun,
  startRun,
  type AnalyzeRequest,
  type CallFilters,
  type PeriodParams,
  type PulseParams,
  type StartRunRequest,
} from '@/shared/api/endpoints'
import type { Analysis, CorpusRun } from '@/shared/api/types'

const HEALTH_REFETCH_MS = 30_000

export const queryKeys = {
  health: ['health'] as const,
  providers: ['providers'] as const,
  taxonomy: ['taxonomy'] as const,
  calls: (filters: CallFilters) => ['calls', filters] as const,
  call: (callId: number) => ['call', callId] as const,
  overview: (params: PeriodParams = {}) =>
    ['dashboard', 'overview', params.month ?? 'no-month', params.anchor ?? 'all-time'] as const,
  agents: (params: PeriodParams = {}) =>
    ['dashboard', 'agents', params.month ?? 'no-month', params.anchor ?? 'all-time'] as const,
  brokers: ['dashboard', 'brokers'] as const,
  signals: (params: PeriodParams = {}) =>
    ['dashboard', 'signals', params.month ?? 'no-month', params.anchor ?? 'all-time'] as const,
  effort: ['dashboard', 'effort'] as const,
  resolutionTime: (params: PeriodParams = {}) =>
    [
      'dashboard',
      'resolution-time',
      params.month ?? 'no-month',
      params.anchor ?? 'all-time',
    ] as const,
  timeValue: (params: PeriodParams = {}) =>
    ['dashboard', 'time-value', params.month ?? 'no-month', params.anchor ?? 'all-time'] as const,
  membersAtRisk: ['dashboard', 'members-at-risk'] as const,
  pulse: (params: PulseParams = {}) =>
    [
      'dashboard',
      'pulse',
      params.month ?? 'no-month',
      params.centre ?? 'no-centre',
      params.anchor ?? 'latest',
      // Part of the key, not just the request: the same anchor bucketed by
      // month is a different answer, and leaving this out served one from the
      // other's cache entry.
      params.bucket ?? 'week',
    ] as const,
  workMix: (params: PeriodParams = {}) =>
    ['dashboard', 'work-mix', params.month ?? 'no-month', params.anchor ?? 'all-time'] as const,
  corpus: ['corpus'] as const,
  corpusImports: ['corpus', 'imports'] as const,
  runs: ['corpus', 'runs'] as const,
  run: (runId: number) => ['corpus', 'run', runId] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: HEALTH_REFETCH_MS,
  })
}

export function useProviders() {
  return useQuery({
    queryKey: queryKeys.providers,
    queryFn: ({ signal }) => fetchProviders(signal),
  })
}

export function useTaxonomy() {
  return useQuery({
    queryKey: queryKeys.taxonomy,
    queryFn: ({ signal }) => fetchTaxonomy(signal),
    // The vocabularies only change when someone edits a config file and
    // restarts, so there is nothing to gain from refetching them.
    staleTime: Infinity,
  })
}

export function useCalls(filters: CallFilters) {
  return useQuery({
    queryKey: queryKeys.calls(filters),
    queryFn: ({ signal }) => fetchCalls(filters, signal),
  })
}

export function useCall(callId: number) {
  return useQuery({
    queryKey: queryKeys.call(callId),
    queryFn: ({ signal }) => fetchCall(callId, signal),
    enabled: Number.isFinite(callId) && callId > 0,
  })
}

export function useOverview(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.overview(params),
    queryFn: ({ signal }) => fetchOverview(params, signal),
    // This query gates the whole Overview page's initial render, including
    // the period filter itself. Without this, picking a different week or
    // month would blank the entire page — filter and all — back to a
    // loading state on every change, since a new period is a query key with
    // no cached data yet.
    placeholderData: keepPreviousData,
  })
}

export function useAgents(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.agents(params),
    queryFn: ({ signal }) => fetchAgents(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useBrokers() {
  return useQuery({ queryKey: queryKeys.brokers, queryFn: ({ signal }) => fetchBrokers(signal) })
}

export function useEffort() {
  return useQuery({ queryKey: queryKeys.effort, queryFn: ({ signal }) => fetchEffort(signal) })
}

export function useResolutionTime(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.resolutionTime(params),
    queryFn: ({ signal }) => fetchResolutionTime(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useTimeValue(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.timeValue(params),
    queryFn: ({ signal }) => fetchTimeValue(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useMembersAtRisk() {
  return useQuery({
    queryKey: queryKeys.membersAtRisk,
    queryFn: ({ signal }) => fetchMembersAtRisk(signal),
  })
}

export function usePulse(params: PulseParams = {}) {
  return useQuery({
    queryKey: queryKeys.pulse(params),
    queryFn: ({ signal }) => fetchPulse(params, signal),
  })
}

export function useWorkMix(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.workMix(params),
    queryFn: ({ signal }) => fetchWorkMix(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useSignals(params: PeriodParams = {}) {
  return useQuery({
    queryKey: queryKeys.signals(params),
    queryFn: ({ signal }) => fetchSignals(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useCorpusStatus() {
  return useQuery({
    queryKey: queryKeys.corpus,
    queryFn: ({ signal }) => fetchCorpusStatus(signal),
  })
}

export function useRuns() {
  return useQuery({ queryKey: queryKeys.runs, queryFn: ({ signal }) => fetchRuns(signal) })
}

export function useRun(runId: number | null) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? 0),
    queryFn: ({ signal }) => fetchRun(runId ?? 0, signal),
    enabled: runId !== null,
  })
}

/**
 * Everything a run changes, refreshed together.
 *
 * A run rewrites the calls it analyzed, so every dashboard figure counted from
 * them is stale the moment it finishes. Invalidating only the run would leave
 * the Overview showing the numbers from before.
 */
function useRunMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<CorpusRun>,
) {
  const client = useQueryClient()

  return useMutation<CorpusRun, Error, TVariables>({
    mutationFn,
    onSuccess: (run) => {
      client.setQueryData(queryKeys.run(run.id), run)
      void client.invalidateQueries({ queryKey: queryKeys.corpus })
    },
  })
}

export function useStartRun() {
  return useRunMutation<StartRunRequest>(startRun)
}

export function useCancelRun() {
  return useRunMutation<number>(cancelRun)
}

export function useResumeRun() {
  return useRunMutation<number>(resumeRun)
}

/**
 * Discard every analyzed call.
 *
 * Invalidates the same keys a finished run does, and for the same reason: the
 * calls are gone, so every dashboard figure counted from them is now wrong.
 */
export function useClearCorpus() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: clearCorpus,
    onSuccess: () => {
      client.removeQueries({ queryKey: queryKeys.corpus })
      void client.invalidateQueries({ queryKey: ['calls'] })
      void client.invalidateQueries({ queryKey: ['dashboard'] })
      void client.invalidateQueries({ queryKey: queryKeys.corpus })
    },
  })
}

/** Called when a run finishes: every figure counted from calls is now stale. */
export function useRefreshAfterRun() {
  const client = useQueryClient()

  return () => {
    void client.invalidateQueries({ queryKey: ['calls'] })
    void client.invalidateQueries({ queryKey: ['dashboard'] })
    void client.invalidateQueries({ queryKey: queryKeys.corpus })
  }
}

export function useAnalyzeTranscript() {
  const client = useQueryClient()

  return useMutation<Analysis, Error, AnalyzeRequest>({
    mutationFn: analyzeTranscript,
    onSuccess: (analysis) => {
      // Seed the detail cache so opening the new call is instant, then
      // invalidate everything counted from stored calls.
      client.setQueryData(queryKeys.call(analysis.id), analysis)
      void client.invalidateQueries({ queryKey: ['calls'] })
      void client.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

/** Corpora that have been imported, newest first. */
export function useCorpusImports() {
  return useQuery({
    queryKey: queryKeys.corpusImports,
    queryFn: ({ signal }) => fetchCorpusImports(signal),
  })
}

/**
 * Import a corpus document.
 *
 * Only the import list is invalidated. Nothing else changes: the import writes
 * to its own directory and analyses nothing, so calls and dashboard figures are
 * exactly as they were.
 */
export function useImportCorpusDocument() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: importCorpusDocument,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.corpusImports })
    },
  })
}
