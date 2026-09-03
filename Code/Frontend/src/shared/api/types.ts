/**
 * Domain types, taken from the generated OpenAPI schema.
 *
 * Nothing here is hand-written. If the backend changes a field, `schema.ts` is
 * regenerated and every consumer of these aliases stops compiling — which is the
 * point: contract drift becomes a build failure rather than a blank panel.
 *
 * Regenerate with `npm run generate:api` (see the script for the backend half).
 */

import type { components } from '@/shared/api/schema'

type Schemas = components['schemas']

export type Analysis = Schemas['AnalysisResponse']
export type CallSummary = Schemas['CallSummaryResponse']
export type CallsPage = Schemas['CallsPageResponse']
export type Marker = Schemas['MarkerResponse']
export type Score = Schemas['ScoreResponse']
export type Layer = Schemas['LayerResponse']
export type Turn = Schemas['TurnResponse']
export type L4Signal = Schemas['L4SignalResponse']
export type BrokerSignal = Schemas['BrokerSignalResponse']
export type AssistEvent = Schemas['AssistEventResponse']
export type Provenance = Schemas['ProvenanceResponse']

export type Provider = Schemas['ProviderResponse']
export type Providers = Schemas['ProvidersResponse']

export type Taxonomy = Schemas['TaxonomyResponse']
export type Category = Schemas['CategoryEntry']

export type Overview = Schemas['OverviewResponse']
export type AgentPerformance = Schemas['AgentResponse']
export type BrokerScorecard = Schemas['BrokerResponse']
export type SignalDistribution = Schemas['SignalsResponse']
export type Effort = Schemas['EffortResponse']
export type ResolutionTime = Schemas['ResolutionTimeResponse']
export type TimeValue = Schemas['TimeValueResponse']
export type MembersAtRisk = Schemas['MembersAtRiskResponse']
export type MemberAtRisk = Schemas['MemberAtRiskResponse']

export type CorpusStatus = Schemas['CorpusStatusResponse']
export type CorpusRun = Schemas['RunResponse']
export type CorpusRunSummary = Schemas['RunSummaryResponse']
export type CorpusRunItem = Schemas['RunItemResponse']
export type RunProgress = Schemas['ProgressResponse']

export type Health = Schemas['HealthResponse']
export type ComponentHealth = Schemas['ComponentHealthResponse']
export type ComponentStatus = ComponentHealth['status']

/** The five layers, in the order the call detail page presents them. */
export const LAYER_ORDER = ['L1', 'L2', 'L3', 'L4', 'L5'] as const
export type LayerId = (typeof LAYER_ORDER)[number]

/** What each layer answers, as the prototype labels it. */
export const LAYER_META: Record<LayerId, { title: string; subtitle: string }> = {
  L1: { title: 'Transcription & understanding', subtitle: 'The foundation' },
  L2: { title: 'What happened', subtitle: 'Call insights' },
  L3: { title: 'How well it was handled', subtitle: 'Agent quality' },
  L4: { title: 'What to do about it', subtitle: 'Operational BI · this call' },
  L5: { title: 'Real-time assist', subtitle: 'Replay — what would have triggered' },
}
