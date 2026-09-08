/**
 * The operations dashboard — the first screen anyone sees.
 *
 * Arranged as three questions in the order a manager asks them: **where we
 * stand**, then **who is affected**, then **the detail behind it**. That
 * ordering is the point of the layout. Before it, the screen opened on a
 * scrolling list of member identifiers and put every total below three tall
 * cards, so the first thing read was the narrowest thing on the page — and
 * nothing anywhere said which way any figure was moving. On this corpus that
 * mattered: resolution reads 54% overall while the weekly series behind it runs
 * 88, 70, 43, 33, 57.
 *
 * The ranked findings that used to head the second tier are a screen of their
 * own now — `features/inferences`. Six items with a paragraph of reasoning each
 * is a worklist somebody owns rather than something read at a glance, and it was
 * pushing the figures a leader steers by below the fold.
 *
 * Every figure here is counted from stored calls; nothing is written by a model.
 * Three presentation rules carry over from the prototype because each of them
 * prevents a specific misreading:
 *
 * * **Median and mean side by side.** The distribution is bimodal, so a single
 *   average sits in a gap where no call falls and hides the weak cluster.
 * * **Zero-count categories are drawn.** An omitted bar reads as "this does not
 *   happen" rather than "this did not happen here".
 * * **Agents below the significance threshold are shown but not rated.** Their
 *   volume is real; a tier on four calls is not.
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  useAgents,
  useOverview,
  usePulse,
  useResolutionTime,
  useTimeValue,
  useSignals,
  useWorkMix,
} from '@/shared/api/queries'
import type { PulseParams } from '@/shared/api/endpoints'
import type { AgentPerformance, Overview } from '@/shared/api/types'
import {
  Bar,
  BarRows,
  DeltaMetric,
  Histogram,
  Legend,
  Metric,
  MetricStrip,
  DualLineTrend,
} from '@/shared/ui/charts'
import { Card, Failure, Loading, Note, PageHeader } from '@/shared/ui/primitives'
import { GraphPeriodFilter, type GraphFilterMode } from './GraphPeriodFilter'
import { PeriodFilter, type Granularity } from './PeriodFilter'
import { addDays } from './weekWindow'
import styles from './OverviewPage.module.css'

/** Half of the graph's 15-day window, in days either side of its centre. */
const GRAPH_WINDOW_HALF_WIDTH_DAYS = 7

/** The graph's own request, given its mode and the day it is currently set
 *  to — any day within a month in month mode, the centre day in week mode. */
function graphPulseParams(mode: GraphFilterMode, value: string | undefined): PulseParams {
  if (!value) return {}
  return mode === 'month' ? { month: value } : { anchor: addDays(value, GRAPH_WINDOW_HALF_WIDTH_DAYS) }
}

/** The prototype's outcome colours. */
const OUTCOME_COLOURS = {
  resolved: '#1F7A4D',
  partial: '#B26A00',
  escalated: '#E08A5D',
  unresolved: '#C8322B',
} as const

/**
 * The outcome a stretch of time bought, worst last.
 *
 * Same four colours as the agent bars, so a reader who has learnt them on one
 * chart does not have to relearn them on another.
 */
const OUTCOME_LEGEND = [
  { resolution: 'RESOLVED', label: 'Resolved', color: OUTCOME_COLOURS.resolved },
  { resolution: 'PARTIALLY RESOLVED', label: 'Partially resolved', color: OUTCOME_COLOURS.partial },
  { resolution: 'ESCALATED', label: 'Escalated', color: OUTCOME_COLOURS.escalated },
  { resolution: 'UNRESOLVED', label: 'Unresolved', color: OUTCOME_COLOURS.unresolved },
] as const

function outcomeLabel(resolution: string): string {
  // Falls back to the stored value so a new outcome is still named, just not
  // prettified — better than an empty tooltip.
  return OUTCOME_LEGEND.find((entry) => entry.resolution === resolution)?.label ?? resolution
}

function outcomeColour(resolution: string): string {
  return (
    OUTCOME_LEGEND.find((entry) => entry.resolution === resolution)?.color ??
    // An outcome the taxonomy gains later still gets a segment, so the bar keeps
    // summing to the total printed beside it.
    '#8A93A3'
  )
}

/** The category bars fade from the brand colour outward. */
const CATEGORY_SHADES = [
  '#14514F',
  '#1E6F6C',
  '#2C8B87',
  '#4BA6A2',
  '#6FBFBB',
  '#9AD4D1',
  '#C9CFD9',
]

const OWNER_COLOUR = '#B26A00'

/**
 * The highest score a histogram bin actually contains.
 *
 * Bins are half-open — `70-80` holds 70 to 79 — except the last, which runs to
 * 100 inclusive so the top score has somewhere to sit. The calls filter's
 * `max_score` is inclusive, so the two have to be reconciled here or every band
 * would pull in the first call of the next one.
 */
function scoreBandCeiling(
  bin: Overview['histogram']['bins'][number],
  bins: Overview['histogram']['bins'],
): number {
  const isLast = bins.at(-1) === bin
  return isLast ? bin.upper : bin.upper - 1
}

/**
 * What getting an answer costs a member.
 *
 * Effort is the churn signal members rarely voice — somebody can report being
 * satisfied and still leave, because the whole episode was exhausting. Shown
 * alongside the quality figures because it answers a different question about
 * the same calls.
 */
function ResolutionTimeCard() {
  const resolution = useResolutionTime()

  if (resolution.isPending) return <Loading what="resolution time" />
  if (resolution.error) return <Failure error={resolution.error} what="resolution time" />

  const data = resolution.data

  if (data.resolved_calls === 0) {
    return (
      <Note>
        No call in this corpus reached a resolution, so there is no time to report. The measure is
        in place; the calls to measure are not.
      </Note>
    )
  }

  const busiest = Math.max(...data.bands.map((band) => band.count), 1)

  return (
    <>
      <div className={styles.effortRow}>
        <div className={styles.effortStat}>
          <b>{data.median_minutes}</b>
          <span>MEDIAN MINUTES TO RESOLVE</span>
        </div>
        <div className={styles.effortStat}>
          <b>{data.resolved_calls}</b>
          <span>OF {data.total_calls} CALLS RESOLVED</span>
        </div>
        <div className={styles.effortStat}>
          <b>{data.longest_minutes}</b>
          <span>LONGEST</span>
        </div>
      </div>

      <div className={styles.bandRow}>
        {data.bands.map((band) => (
          <div key={band.label} className={styles.band}>
            <div className={styles.bandTrack}>
              {/* A zero band keeps its bar stub. An absent bar reads as "this
                  does not happen" rather than "this did not happen here". */}
              <i style={{ height: `${String(Math.max((band.count * 100) / busiest, 3))}%` }} />
            </div>
            <b>{band.count}</b>
            <span>{band.label} MIN</span>
          </div>
        ))}
      </div>

      <BarRows>
        {data.categories.map((category) => (
          <Bar
            key={category.code}
            // Resolved only, matching the card. Without the outcome the link
            // would open every call in the category and quietly contradict the
            // count it was opened from.
            label={drillDown(
              category.label,
              `category=${encodeURIComponent(category.code)}&resolution=RESOLVED`,
              category.resolved_calls > 0,
            )}
            title={`${category.label}: ${String(category.resolved_calls)} resolved, longest ${String(category.longest_minutes)} min`}
            segments={[
              {
                value: category.median_minutes,
                color: OWNER_COLOUR,
                label: category.label,
              },
              {
                // Scaled against the slowest category so the bars are
                // comparable rather than each filling its own row.
                value: Math.max(data.longest_minutes - category.median_minutes, 0),
                color: 'transparent',
                label: 'Remainder',
              },
            ]}
            value={category.resolved_calls === 0 ? '—' : `${String(category.median_minutes)} min`}
          />
        ))}
      </BarRows>
    </>
  )
}

/**
 * What the time on calls bought.
 *
 * The only panel here that counts minutes rather than calls. "How long is a
 * call" is an operations question; "how many of our hours produced an answer"
 * is the one a manager answers for, and it is a different number.
 */
function TimeValueCard() {
  const time = useTimeValue()

  if (time.isPending) return <Loading what="the time ledger" />
  if (time.error) return <Failure error={time.error} what="the time ledger" />

  const data = time.data

  if (data.total_minutes === 0) {
    return (
      <Note>
        No call in this corpus has a recorded duration, so there are no minutes to account for.
      </Note>
    )
  }

  const hours = (data.total_minutes / 60).toFixed(1)
  const widest = Math.max(...data.categories.map((entry) => entry.total_minutes), 1)

  return (
    <>
      <div className={styles.effortRow}>
        <div className={styles.effortStat}>
          <b>{hours}h</b>
          <span>TOTAL TIME ON CALLS</span>
        </div>
        <div className={styles.effortStat}>
          <b>{data.productive_share}%</b>
          <span>BOUGHT A RESOLUTION</span>
        </div>
        <div className={styles.effortStat}>
          <b>{(data.unproductive_minutes / 60).toFixed(1)}h</b>
          <span>BOUGHT NOTHING</span>
        </div>
      </div>

      <Legend
        items={OUTCOME_LEGEND.map((entry) => ({ label: entry.label, color: entry.color }))}
      />
      <BarRows>
        {data.categories.map((category) => (
          <Bar
            key={category.code}
            // Every outcome, because the bar is every outcome — this card
            // counts the minutes a category claimed, not the ones it earned.
            label={drillDown(
              category.label,
              `category=${encodeURIComponent(category.code)}`,
              category.total_minutes > 0,
            )}
            title={`${category.label}: ${String(category.total_minutes)} min, ${String(category.unproductive_share)}% bought no resolution`}
            segments={[
              ...category.by_outcome.map((outcome) => ({
                value: outcome.minutes,
                color: outcomeColour(outcome.resolution),
                // Bar appends the value, so the label is the name alone.
                label: outcomeLabel(outcome.resolution),
              })),
              {
                // Scaled against the biggest claim on the centre's time, so the
                // bars compare as absolute minutes rather than each filling its
                // own row and hiding which work costs most.
                value: Math.max(widest - category.total_minutes, 0),
                color: 'transparent',
                label: 'Remainder',
              },
            ]}
            value={`${String(category.total_minutes)} min`}
          />
        ))}
      </BarRows>

      <div className={styles.failureModes}>
        {[
          { key: 'fast', title: 'Ended early, unresolved', mode: data.fast_fail },
          { key: 'slow', title: 'Ran long, still unresolved', mode: data.slow_fail },
        ].map((entry) => (
          <div key={entry.key} className={styles.failureMode}>
            <h5>{entry.title}</h5>
            <div className={styles.failureFigures}>
              <b>{entry.mode.calls}</b>
              <span>
                CALLS · {entry.mode.minutes} MIN · AVG SCORE {entry.mode.average_score}
              </span>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}


function ResolutionByAgent({ agents }: { agents: readonly AgentPerformance[] }) {
  if (agents.length === 0) {
    return <Note>No agents have been named in an analyzed call yet.</Note>
  }

  // Rated agents first, then the rest, and within each group by the score the
  // row shows. The two groups stay apart because a tier is a claim about an
  // agent and a thin average is not, and mixing them would rank a three-call
  // figure against a settled one. Ordering the second group by score too, now
  // that it has one: ordering visible numbers by an invisible call count reads
  // as no order at all. Sorting a copy — the query cache's array must not be
  // mutated.
  const ranked = [...agents].sort((a, b) => {
    if (Boolean(a.tier) !== Boolean(b.tier)) return a.tier ? -1 : 1
    return b.average_score - a.average_score || a.agent_name.localeCompare(b.agent_name)
  })

  return (
    <>
      <BarRows>
        {ranked.map((agent) => (
          <Bar
            key={agent.agent_name}
            label={
              // Straight to this agent's calls: the bar shows that something is
              // wrong, and the next question is always "which calls?".
              <Link to={`/calls?agent=${encodeURIComponent(agent.agent_name)}`}>
                {agent.agent_name} · {agent.call_count}
              </Link>
            }
            title={
              agent.tier
                ? `${agent.agent_name}: ${agent.tier}`
                : `${agent.agent_name}: ${agent.note ?? 'not rated'}`
            }
            segments={[
              { value: agent.resolved, color: OUTCOME_COLOURS.resolved, label: 'Resolved' },
              {
                value: agent.partially_resolved,
                color: OUTCOME_COLOURS.partial,
                label: 'Partial',
              },
              { value: agent.escalated, color: OUTCOME_COLOURS.escalated, label: 'Escalated' },
              { value: agent.unresolved, color: OUTCOME_COLOURS.unresolved, label: 'Unresolved' },
            ]}
            value={
              agent.tier ? (
                Math.round(agent.average_score)
              ) : (
                // Shown, but not as a settled figure. The average is real
                // arithmetic on every call the agent took; what the threshold
                // withholds is the tier, because one call moves a four-call
                // average by four points and a GOOD/AVERAGE boundary should not
                // turn on that. Muted and marked so the difference is visible
                // without a reader having to know the rule — the mark's meaning
                // is on the row's tooltip and in the card's hint.
                <span className={styles.provisionalScore} title={agent.note ?? 'Not tier-rated'}>
                  {Math.round(agent.average_score)}
                  <span aria-hidden="true">*</span>
                  <span className={styles.visuallyHidden}>
                    , {agent.note ?? 'not tier-rated'}
                  </span>
                </span>
              )
            }
          />
        ))}
      </BarRows>
      <Legend
        items={[
          { label: 'Resolved', color: OUTCOME_COLOURS.resolved },
          { label: 'Partial', color: OUTCOME_COLOURS.partial },
          { label: 'Escalated', color: OUTCOME_COLOURS.escalated },
          { label: 'Unresolved', color: OUTCOME_COLOURS.unresolved },
        ]}
      />
    </>
  )
}

/** Percentage change between two figures, or `null` when there is nothing to
 *  divide by — a previous-period reading of zero is a gap, not a meaningful
 *  "infinite" swing. */
function percentChange(
  current: number | null | undefined,
  previous: number | null | undefined,
): number | null {
  if (current === null || current === undefined || !previous) {
    return null
  }
  return ((current - previous) / previous) * 100
}

function PulseStrip({ anchor }: { anchor: string | undefined }) {
  const pulse = usePulse(anchor ? { anchor } : {})

  if (pulse.isPending) return <Loading what="this week" />
  if (pulse.error) return <Failure error={pulse.error} what="the weekly trend" />
  const { latest, previous, delta } = pulse.data

  if (!latest) {
    return <Note>No call carries a start time, so there is no week to report.</Note>
  }

  return (
    <MetricStrip>
      <DeltaMetric
        label="Calls Monitored"
        value={latest.calls}
        delta={percentChange(latest.calls, previous?.calls)}
        format={(value) => `${value.toFixed(1)}%`}
        goodDirection="neutral"
      />
      <DeltaMetric
        label="First Call Resolution (FCR)"
        value={latest.resolution_rate === null ? '—' : `${String(latest.resolution_rate)}%`}
        delta={delta?.resolution_rate}
        format={(value) => `${String(value)} pts`}
        goodDirection="up"
      />
      <DeltaMetric
        label="Average Call Score"
        value={latest.median_score ?? '—'}
        delta={delta?.median_score}
        format={(value) => `${String(value)} pts`}
        goodDirection="up"
      />
      <DeltaMetric
        label="Average Handling Time (AHT)"
        value={
          latest.median_handle_minutes === null
            ? '—'
            : `${String(latest.median_handle_minutes)}m`
        }
        delta={delta?.median_handle_minutes}
        format={(value) => `${String(value)} min`}
        // Neither direction is good on its own. A shorter call is an answer
        // found faster or a member brushed off, and this figure cannot tell
        // them apart — the card below it can.
        goodDirection="neutral"
      />
    </MetricStrip>
  )
}

function QualityVsHandlingTimeCard({ params }: { params: PulseParams }) {
  const pulse = usePulse(params)

  if (pulse.isPending) return <Loading what="the trend" />
  if (pulse.error) return <Failure error={pulse.error} what="the weekly trend" />
  const { points } = pulse.data
  if (points.length === 0) return null

  return (
    <DualLineTrend
      // Taller than the shared default of 220, because this is the one place
      // the chart is drawn full width. The plot stretches to its box
      // (`preserveAspectRatio="none"`), so at roughly 1180px wide and 220 tall
      // it was a 5:1 letterbox: a fifteen-point swing in quality arrived as a
      // line a few pixels off flat, and the whole reason the card exists is to
      // say which way the figures are moving. At 340 the box is nearer 3.5:1
      // and the same swing is legible. Safe to change freely — both lines carry
      // `vector-effect: non-scaling-stroke`, so stroke weight does not stretch
      // with the box.
      height={340}
      points={points.map((point) => ({
        label: point.label,
        quality: point.median_score ?? null,
        ahtMinutes: point.median_handle_minutes ?? null,
      }))}
    />
  )
}

/**
 * A bar's label, as a way into the calls behind it.
 *
 * Every drill-down on this page obeys one rule: a bar with nothing in it is not
 * a link. There is nothing to open, and a link to an empty list reads as a
 * fault rather than as an answer — which is the same reason an empty histogram
 * bar stays inert.
 *
 * The query is the caller's, because only the caller knows which calls its bar
 * counted. "How long an answer takes" draws resolved calls only, so its link
 * has to say so or it would open a set larger than the figure it came from.
 */
function drillDown(label: string, query: string, populated: boolean) {
  if (!populated) return label
  return <Link to={`/calls?${query}`}>{label}</Link>
}

/** "MEMBER" and 28 calls, as "Member · 28". */
function callerLabel(caller: { caller_type: string; calls: number }): string {
  const name = `${caller.caller_type.charAt(0)}${caller.caller_type.slice(1).toLowerCase()}`
  return `${name} · ${String(caller.calls)}`
}

function CallerMixCard() {
  const mix = useWorkMix()

  if (mix.isPending) return <Loading what="the caller mix" />
  if (mix.error) return <Failure error={mix.error} what="the caller mix" />

  return (
    <>
      <BarRows>
        {mix.data.callers.map((caller) => (
          <Bar
            key={caller.caller_type}
            label={drillDown(
              callerLabel(caller),
              `caller=${encodeURIComponent(caller.caller_type)}`,
              caller.calls > 0,
            )}
            segments={[
              {
                value: caller.resolution_rate,
                color: OUTCOME_COLOURS.resolved,
                label: 'First Call Resolution (FCR)',
              },
              {
                value: Math.max(100 - caller.resolution_rate, 0),
                color: OUTCOME_COLOURS.unresolved,
                label: 'Not resolved on first call',
              },
            ]}
            value={caller.calls === 0 ? '—' : `${String(caller.resolution_rate)}%`}
          />
        ))}
      </BarRows>
      {mix.data.unattributed_calls > 0 ? (
        <Note>
          <b>{mix.data.unattributed_calls}</b>{' '}
          {mix.data.unattributed_calls === 1 ? 'call states' : 'calls state'} no caller and
          {mix.data.unattributed_calls === 1 ? ' is' : ' are'} left out.
        </Note>
      ) : null}
    </>
  )
}

function HourlyCard() {
  const navigate = useNavigate()
  const mix = useWorkMix()
  const weakest = mix.data?.weakest_hour

  if (mix.isPending) return <Loading what="the day" />
  if (mix.error) return <Failure error={mix.error} what="the hourly load" />
  if (mix.data.hours.length === 0) return null

  const peak = Math.max(...mix.data.hours.map((hour) => hour.calls), 1)

  return (
    <>
      <Histogram
        peak={peak}
        bars={mix.data.hours.map((hour) => ({
          label: hour.label.slice(0, 2),
          count: hour.calls,
          // Marked, not merely low: this is the hour a rota would change for.
          isBelowThreshold: hour.label === weakest,
          // "Which calls?" is the next question after "which hour?", and a
          // rota argument is won with the calls rather than with the bar.
          selectLabel: `Show the ${String(hour.calls)} ${
            hour.calls === 1 ? 'call' : 'calls'
          } that started at ${hour.label}`,
          onSelect: () => {
            navigate(`/calls?hour=${String(hour.hour)}`)
          },
        }))}
      />
    </>
  )
}

export function OverviewPage() {
  const navigate = useNavigate()
  const overview = useOverview()
  const agents = useAgents()
  const signals = useSignals()

  // The header filter drives the metric cards. The graph's own filter is
  // seeded from it — mode and all — but only at the moment the header filter
  // itself changes; from then on the two are independent, which is why the
  // graph's mode and value get their own state rather than being derived
  // from the header's on every render.
  const [globalAnchor, setGlobalAnchor] = useState<string | undefined>(undefined)
  const [globalGranularity, setGlobalGranularity] = useState<Granularity>('week')
  const [graphMode, setGraphMode] = useState<GraphFilterMode>('week')
  const [graphValue, setGraphValue] = useState<string | undefined>(undefined)
  useEffect(() => {
    setGraphMode(globalGranularity)
    setGraphValue(globalAnchor)
  }, [globalAnchor, globalGranularity])

  // A stable query — its key never changes — purely to source the calendar
  // pickers' available weeks and the corpus's true latest week. Sourcing
  // that from the header's or the graph's own pulse query instead would
  // unmount the pickers (and any state they hold) every time their own
  // anchor changed, since each anchor is a different query that starts back
  // at "no data yet".
  const corpus = usePulse()
  const availableWeeks = corpus.data?.available_weeks ?? []
  const latestWeek = corpus.data?.latest?.starting
  // Both pickers need a concrete day to draw themselves around even before a
  // reader has ever touched them.
  const resolvedGraphValue = graphValue ?? latestWeek
  const graphParams = graphPulseParams(graphMode, resolvedGraphValue)

  if (overview.isPending) {
    return <Loading what="the dashboard" />
  }
  if (overview.error) {
    return <Failure error={overview.error} what="the dashboard" />
  }

  const { metrics, histogram, categories } = overview.data

  if (metrics.total_calls === 0) {
    return (
      <>
        <PageHeader title="Operations dashboard" />
        <Card title="No calls analyzed yet">
          <Note>
            Every figure on this screen is counted from analyzed calls. Start with{' '}
            <Link to="/analyze">Analyze a call</Link>.
          </Note>
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Operations dashboard"
        actions={
          <PeriodFilter
            availableWeeks={availableWeeks}
            anchor={globalAnchor}
            onChange={setGlobalAnchor}
            onGranularityChange={setGlobalGranularity}
          />
        }
      />

      {/* --- Where we stand -------------------------------------------------
          The first viewport answers "which way are we going", which is what a
          leader manages against. It used to answer "who is at risk" — a
          scrolling list of member identifiers — while the totals sat fifteen
          hundred pixels below it and carried no direction at all. */}
      <PulseStrip anchor={globalAnchor} />

      {/* --- The detail behind it ---------------------------------------------
          Kept in full, and moved up beside the figures it elaborates on —
          it used to sit below the coaching charts, level with material that
          answers a different question entirely. */}
      <MetricStrip>
        <Metric label="Calls analyzed" value={metrics.total_calls} sub="From stored analyses" />
        <Metric
          label="Average Call Score"
          value={metrics.median_score}
          sub={
            <>
              Median of every call; mean <b>{metrics.mean_score}</b>
              {metrics.median_score === metrics.mean_score
                ? ' — distribution is even'
                : ' — distribution is split'}
            </>
          }
        />
        <Metric
          label="First Call Resolution (FCR)"
          value={`${String(metrics.first_contact_resolution_rate)}%`}
          sub={
            <>
              Industry range <b>65–75%</b>
            </>
          }
        />
        <Metric
          label="Escalation rate"
          value={`${String(metrics.escalation_rate)}%`}
          sub={
            // A flat 0% beside an industry range reads as a broken feed. It is
            // not: no call in this corpus was ever marked escalated, and saying
            // so is the difference between a finding and a suspected bug.
            metrics.escalation_rate === 0 ? (
              <>No analyzed call was escalated</>
            ) : (
              <>
                Industry range <b>8–12%</b>
              </>
            )
          }
        />
        <Metric
          label="Broker-attributed"
          value={metrics.broker_signal_count}
          sub={
            <>
              Across <b>{metrics.distinct_broker_count}</b> named brokers
            </>
          }
        />
      </MetricStrip>

      <Card
        className={styles.solo}
        title="Overall Call Quality vs Average Handling Time"
        hint="Two lines over time, each read against its own axis: quality on the left, out of 100; handling time on the right, in minutes. Hover or focus a week for both exact numbers. A week that measured nothing breaks the line rather than being drawn through, so a gap is missing data and not a collapse. In 3-week mode, shows the three weeks centred on whichever week is picked below — the week itself, the one before it, and the one after. In Month mode, shows every week of the picked month."
        actions={
          resolvedGraphValue ? (
            <GraphPeriodFilter
              mode={graphMode}
              onModeChange={setGraphMode}
              value={resolvedGraphValue}
              onChange={setGraphValue}
            />
          ) : null
        }
      >
        <QualityVsHandlingTimeCard params={graphParams} />
      </Card>

      {/* --- Who is affected -------------------------------------------------
          What used to be "where it is going wrong", minus the queue that named
          the problems — that is its own screen now, at /inferences. What is
          left says who is on the receiving end: the population being failed,
          the team who owns it, and the hours it burns. Ordered by what a leader
          acts on rather than by how the figures are computed.

          The members-at-risk matrix used to open this section and now lives on
          /inferences beside the findings. It was the one card here that named
          individuals and asked for follow-up on each, which is a worklist
          rather than a reading — and at eight members against five warning
          signs it was never answering "is anything wrong" in a glance. */}
      {/* Paired because they answer the same question from opposite ends —
          which callers are failed, and which team owns the failure. They are
          also within fifty pixels of each other in height, so neither card
          leaves a void beside the other. */}
      <div className={styles.grid}>
        <Card
          title="Who calls, and who gets an answer"
          hint="Bars are the share of each population resolved first time, not their share of the queue — the three are different sizes, and stacking them by volume would say only that members call most. An employer is a whole group’s coverage and a broker is a distribution channel; averaging all three into one resolution rate describes none of them."
        >
          <CallerMixCard />
        </Card>

        <Card
          title="Signals by owner"
          hint="A call raising findings for two teams is counted for the team owning the more serious one, so no call appears twice. Owners with no signals are drawn so the absence is visible rather than implied."
        >
          {signals.isPending ? <Loading what="signals" /> : null}
          {signals.error ? <Failure error={signals.error} what="signal distribution" /> : null}
          {signals.data ? (
            <>
              <BarRows>
                {signals.data.owners.map((owner) => (
                  <Bar
                    key={owner.owner}
                    label={owner.owner}
                    segments={[
                      { value: owner.count, color: OWNER_COLOUR, label: owner.owner },
                      {
                        value: Math.max(metrics.total_calls - owner.count, 0),
                        color: 'transparent',
                        label: 'Remainder',
                      },
                    ]}
                    value={owner.count === 0 ? '—' : owner.count}
                  />
                ))}
              </BarRows>
            </>
          ) : null}
        </Card>
      </div>

      <Card
        className={styles.solo}
        title="Productive and unproductive minutes"
        hint="The two failure modes need opposite responses. Ending early and unresolved is a member brushed off, which is a coaching signal; running long and still unresolved is a process problem, where coaching the agent would be the wrong response. They are split at the median length of a call that did resolve — derived from this corpus rather than configured, so the line stays comparable as the mix of work changes. Calls with no recorded duration are left out entirely rather than counted as zero, which would understate the minutes."
      >
        <TimeValueCard />
      </Card>

      {/* The two tallest cards on the page share a row, and the two shortest
          share the next one. Paired by subject alone, a 198px histogram sat
          beside a 461px agent list and left a quarter of its card empty. */}
      <div className={styles.grid}>
        <Card
          title="Resolution by agent"
          hint="Every agent's average is shown; a starred one is not tier-rated, because the agent has fewer calls than the significance threshold. The average is real arithmetic either way — what is withheld is the GOOD, AVERAGE or POOR label, since one call moves a four-call average by four points and a tier boundary should not turn on that. The bars are outcomes, not the score: they show how the agent's calls ended."
        >
          {agents.isPending ? <Loading what="agents" /> : null}
          {agents.error ? <Failure error={agents.error} what="agent performance" /> : null}
          {agents.data ? <ResolutionByAgent agents={agents.data} /> : null}
        </Card>

        <Card
          title="How long an answer takes"
          hint="Median minutes to resolve, slowest category first, over the calls that reached a resolution. A category that has resolved nothing shows a dash rather than a zero, because no time was measured — not a fast one."
        >
          <ResolutionTimeCard />
        </Card>
      </div>

      {/* The hourly chart is third and so takes the full row. It is the one
          chart here that gains from the width: a rota is read hour by hour. */}
      <div className={styles.grid}>
        <Card
          title="Score distribution"
          hint="Coach the cluster below the threshold; the rest needs no intervention. Bins are half-open — 70–80 holds 70 to 79 — except the last, which runs to 100 inclusive so the top score has somewhere to sit. Press a bar to open the calls in it."
        >
          <Histogram
            bars={histogram.bins.map((bin) => {
              const highest = scoreBandCeiling(bin, histogram.bins)
              return {
                label: bin.label,
                count: bin.count,
                isBelowThreshold: bin.is_below_threshold,
                selectLabel: `Show the ${String(bin.count)} ${
                  bin.count === 1 ? 'call' : 'calls'
                } scoring ${String(bin.lower)} to ${String(highest)}`,
                onSelect: () => {
                  navigate(`/calls?min_score=${String(bin.lower)}&max_score=${String(highest)}`)
                },
              }
            })}
            peak={histogram.peak}
          />
        </Card>

        <Card
          title="What members call about"
          hint="A zero-count category is drawn rather than omitted: an absent bar reads as “this does not happen” rather than “this did not happen here”. If coverage drops below 90% the categories need revising, not the chart."
        >
          <BarRows>
            {categories.map((category, index) => (
              <Bar
                key={category.code}
                label={drillDown(
                  category.label,
                  `category=${encodeURIComponent(category.code)}`,
                  category.count > 0,
                )}
                segments={[
                  {
                    value: category.count,
                    color: CATEGORY_SHADES[index % CATEGORY_SHADES.length] ?? '#14514F',
                    label: category.label,
                  },
                  {
                    // The remainder keeps every bar on the same scale.
                    value: Math.max(metrics.total_calls - category.count, 0),
                    color: 'transparent',
                    label: 'Other calls',
                  },
                ]}
                value={category.count}
              />
            ))}
          </BarRows>
        </Card>

        <Card
          title="Hourly call distribution"
          hint="Calls by the hour they started. The marked hour is a staffing question rather than a coaching one. Hours with fewer than four calls are drawn but carry no finding: a rota changed on two calls is a rota changed on noise."
        >
          <HourlyCard />
        </Card>
      </div>

    </>
  )
}
