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
  fetchAgents,
  fetchBrokers,
  fetchCall,
  fetchCalls,
  fetchHealth,
  fetchOverview,
  fetchProviders,
  fetchSignals,
  fetchTaxonomy,
  type AnalyzeRequest,
  type CallFilters,
} from '@/shared/api/endpoints'
import type { Analysis } from '@/shared/api/types'

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

export function useSignals() {
  return useQuery({ queryKey: queryKeys.signals, queryFn: ({ signal }) => fetchSignals(signal) })
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
