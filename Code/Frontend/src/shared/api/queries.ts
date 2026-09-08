/**
 * React Query hooks.
 *
 * Query keys are declared once here so an invalidation cannot miss a consumer:
 * analysing a call must refresh the calls list and every dashboard figure, since
 * all of them are counted from the same stored calls.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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
  overview: ['dashboard', 'overview'] as const,
  agents: ['dashboard', 'agents'] as const,
  brokers: ['dashboard', 'brokers'] as const,
  signals: ['dashboard', 'signals'] as const,
  effort: ['dashboard', 'effort'] as const,
  resolutionTime: ['dashboard', 'resolution-time'] as const,
  timeValue: ['dashboard', 'time-value'] as const,
  membersAtRisk: ['dashboard', 'members-at-risk'] as const,
  pulse: ['dashboard', 'pulse'] as const,
  workMix: ['dashboard', 'work-mix'] as const,
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

export function useOverview() {
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: ({ signal }) => fetchOverview(signal),
  })
}

export function useAgents() {
  return useQuery({ queryKey: queryKeys.agents, queryFn: ({ signal }) => fetchAgents(signal) })
}

export function useBrokers() {
  return useQuery({ queryKey: queryKeys.brokers, queryFn: ({ signal }) => fetchBrokers(signal) })
}

export function useEffort() {
  return useQuery({ queryKey: queryKeys.effort, queryFn: ({ signal }) => fetchEffort(signal) })
}

export function useResolutionTime() {
  return useQuery({
    queryKey: queryKeys.resolutionTime,
    queryFn: ({ signal }) => fetchResolutionTime(signal),
  })
}

export function useTimeValue() {
  return useQuery({
    queryKey: queryKeys.timeValue,
    queryFn: ({ signal }) => fetchTimeValue(signal),
  })
}

export function useMembersAtRisk() {
  return useQuery({
    queryKey: queryKeys.membersAtRisk,
    queryFn: ({ signal }) => fetchMembersAtRisk(signal),
  })
}

export function usePulse() {
  return useQuery({ queryKey: queryKeys.pulse, queryFn: ({ signal }) => fetchPulse(signal) })
}

export function useWorkMix() {
  return useQuery({ queryKey: queryKeys.workMix, queryFn: ({ signal }) => fetchWorkMix(signal) })
}

export function useSignals() {
  return useQuery({ queryKey: queryKeys.signals, queryFn: ({ signal }) => fetchSignals(signal) })
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
