/**
 * "What needs attention" — the first screen anyone sees.
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

import { Link, useNavigate } from 'react-router-dom'

import {
  useAgents,
  useMembersAtRisk,
  useOverview,
  useResolutionTime,
  useTimeValue,
  useSignals,
} from '@/shared/api/queries'
import type { AgentPerformance, Overview } from '@/shared/api/types'
import { Bar, BarRows, Histogram, Legend, Metric, MetricStrip } from '@/shared/ui/charts'
import { Card, Chip, Failure, Loading, Note, PageHeader } from '@/shared/ui/primitives'
import { cx } from '@/shared/ui/cx'
import styles from './OverviewPage.module.css'

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

function severityClass(severity: string): string | undefined {
  if (severity === 'CRITICAL' || severity === 'HIGH') return styles.itemHigh
  if (severity === 'MEDIUM') return styles.itemMedium
  return styles.itemLow
}

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
 * How many calls the owner bars account for.
 *
 * Each call is attributed to exactly one owner, so this is the number of calls
 * carrying at least one signal — not a sum of findings.
 */
function ownerTotal(owners: readonly { count: number }[]): number {
  return owners.reduce((sum, owner) => sum + owner.count, 0)
}

function AttentionQueue({ items }: { items: Overview['attention'] }) {
  if (items.length === 0) {
    return (
      <Card title="What needs attention">
        <Note>
          Nothing has crossed a threshold. This means the rules ran and found nothing, not that
          nothing was checked — the thresholds live in <code>dashboard.yaml</code>.
        </Note>
      </Card>
    )
  }

  return (
    <div className={styles.queue}>
      {items.map((item) => (
        <article
          key={`${item.rule_id}-${item.subject}`}
          className={cx(styles.item, severityClass(item.severity))}
        >
          <div>
            <h4>{item.title}</h4>
            <p className={styles.why}>{item.why}</p>
            <div className={styles.meta}>
              <span className={styles.owner}>{item.owner}</span>
              <Chip tone="high">{item.severity}</Chip>
              {item.references.length > 0 ? (
                <span className={styles.reference}>
                  <Chip>{item.references.slice(0, 6).join(' ')}</Chip>
                </span>
              ) : null}
            </div>
          </div>
          <div className={styles.count}>
            <b>{item.count}</b>
            <span>
              {item.unresolved > 0 ? `CALLS · ${String(item.unresolved)} OPEN` : 'CALLS'}
            </span>
          </div>
        </article>
      ))}
    </div>
  )
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
            label={category.label}
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
      <Note>
        Median minutes to resolve, slowest first, over the <b>{data.resolved_calls}</b> calls that
        reached a resolution. A category that has resolved nothing shows a dash rather than a zero,
        because no time was measured — not a fast one.
      </Note>
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
            label={category.label}
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
          {
            key: 'fast',
            title: 'Ended early, unresolved',
            mode: data.fast_fail,
            reading: 'Shorter than a call that works — the member was brushed off. Coaching.',
          },
          {
            key: 'slow',
            title: 'Ran long, still unresolved',
            mode: data.slow_fail,
            reading:
              'The work was done and no answer existed. A process problem — coaching these agents would be the wrong response.',
          },
        ].map((entry) => (
          <div key={entry.key} className={styles.failureMode}>
            <h5>{entry.title}</h5>
            <div className={styles.failureFigures}>
              <b>{entry.mode.calls}</b>
              <span>
                CALLS · {entry.mode.minutes} MIN · AVG SCORE {entry.mode.average_score}
              </span>
            </div>
            <p>{entry.reading}</p>
          </div>
        ))}
      </div>
      <Note>
        Split at <b>{data.resolved_median_minutes} minutes</b>, the median length of a call that
        did resolve — derived from this corpus rather than configured, so it stays comparable as
        the mix of work changes.
      </Note>
    </>
  )
}

/**
 * Members showing signs of leaving.
 *
 * Deliberately not a churn score. Nothing here has been measured against a real
 * departure, so the card names the signs each member is carrying and leaves the
 * judgement to whoever reads it — a percentage would be indistinguishable from a
 * measured one while being invented.
 */
function MembersAtRisk() {
  const members = useMembersAtRisk()

  if (members.isPending) return <Loading what="members at risk" />
  if (members.error) return <Failure error={members.error} what="members at risk" />

  if (members.data.members.length === 0) {
    return <Note>No member is showing a warning sign. Shown as a result, not an omission.</Note>
  }

  return (
    <>
      <div className={styles.memberList}>
        {members.data.members.map((member) => (
          <article key={member.member_id} className={styles.member}>
            <div>
              <h4>
                {/* Filtered by member, not searched by reference: a search
                    finds one call, and the point of this row is all of them. */}
                <Link to={`/calls?member=${encodeURIComponent(member.member_id)}`}>
                  {member.member_name ? (
                    <>
                      {member.member_name}{' '}
                      {/* The identifier stays visible rather than being replaced:
                          it is what the calls list filters on and what anyone
                          looking the member up in another system will need. */}
                      <span className={styles.memberId}>({member.member_id})</span>
                    </>
                  ) : (
                    // No call of theirs stated a name. The identifier alone is
                    // still true; a placeholder like "Unknown" would not be.
                    member.member_id
                  )}
                </Link>
              </h4>
              <div className={styles.meta}>
                {member.factor_labels.map((label) => (
                  <Chip key={label} tone="high">
                    {label}
                  </Chip>
                ))}
              </div>
            </div>
            <div className={styles.count}>
              <b>{member.factors.length}</b>
              <span>
                {member.call_count === 1 ? '1 CALL' : `${String(member.call_count)} CALLS`}
              </span>
            </div>
          </article>
        ))}
      </div>
      <Note>
        Ranked by how many warning signs a member shows, not by a predicted probability. No factor
        here has yet been measured against a member who actually left.
      </Note>
    </>
  )
}

function ResolutionByAgent({ agents }: { agents: readonly AgentPerformance[] }) {
  if (agents.length === 0) {
    return <Note>No agents have been named in an analysed call yet.</Note>
  }

  // Ordered by the figure each row actually shows. An agent below the
  // significance threshold has no score to sort on — a dash cannot be ranked
  // against a number — so those fall to the bottom ordered by call count, which
  // puts the ones closest to earning a rating first. Sorting a copy: the query
  // cache's array must not be mutated.
  const ranked = [...agents].sort((a, b) => {
    if (a.tier && b.tier) {
      return b.average_score - a.average_score || a.agent_name.localeCompare(b.agent_name)
    }
    if (a.tier) return -1
    if (b.tier) return 1
    return b.call_count - a.call_count || a.agent_name.localeCompare(b.agent_name)
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
            value={agent.tier ? Math.round(agent.average_score) : '—'}
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
      <Note>
        Agents with too few calls are shown but not tier-rated — the sample is too small to be
        fair, and their score reads as a dash.
      </Note>
    </>
  )
}

export function OverviewPage() {
  const navigate = useNavigate()
  const overview = useOverview()
  const agents = useAgents()
  const signals = useSignals()

  if (overview.isPending) {
    return <Loading what="the dashboard" />
  }
  if (overview.error) {
    return <Failure error={overview.error} what="the dashboard" />
  }

  const { metrics, histogram, categories, attention } = overview.data

  if (metrics.total_calls === 0) {
    return (
      <>
        <PageHeader title="What needs attention" />
        <Card title="No calls analysed yet">
          <Note>
            Every figure on this screen is counted from analysed calls. Start with{' '}
            <Link to="/analyze">Analyze a call</Link>.
          </Note>
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="What needs attention"
        subtitle="Ranked by severity then calls affected. Every item has an owner."
      />

      <div className={styles.grid}>
        <Card
          title="Members at risk"
          subtitle="Warning signs observed, not a prediction — no factor here is validated yet."
        >
          <MembersAtRisk />
        </Card>

        <Card
          title="How long an answer takes"
          subtitle="Resolved calls only — the quickest way to end a call is to solve nothing."
        >
          <ResolutionTimeCard />
        </Card>
      </div>

      <AttentionQueue items={attention} />

      <div className={styles.eyebrow}>Volume and outcomes</div>
      <MetricStrip>
        <Metric label="Calls analysed" value={metrics.total_calls} sub="From stored analyses" />
        <Metric
          label="Median agent score"
          value={metrics.median_score}
          sub={
            <>
              Mean <b>{metrics.mean_score}</b>
              {metrics.median_score === metrics.mean_score
                ? ' — distribution is even'
                : ' — distribution is split'}
            </>
          }
        />
        <Metric
          label="First-contact resolution"
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
            <>
              Industry range <b>8–12%</b>
            </>
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

      <div className={styles.grid} style={{ marginTop: 22 }}>
        <Card
          title="Agent score distribution"
          subtitle="Reporting one average would hide the low cluster."
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
          <Note>
            {histogram.below_threshold_count} call
            {histogram.below_threshold_count === 1 ? '' : 's'} fall below the coaching threshold.
            Coach that cluster; the rest needs no intervention.
          </Note>
        </Card>

        <Card
          title="Resolution by agent"
          subtitle="Proportional, so volume does not distort the picture."
        >
          {agents.isPending ? <Loading what="agents" /> : null}
          {agents.error ? <Failure error={agents.error} what="agent performance" /> : null}
          {agents.data ? <ResolutionByAgent agents={agents.data} /> : null}
        </Card>
      </div>

      <div className={styles.grid}>
        <Card
          title="What members call about"
          subtitle="Every configured category, including those with no calls."
        >
          <BarRows>
            {categories.map((category, index) => (
              <Bar
                key={category.code}
                label={category.label}
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
          <Note>
            Taxonomy coverage <b>{overview.data.taxonomy_coverage}%</b>. If this drops below 90%
            the categories need revising, not the chart.
          </Note>
        </Card>

        <Card
          title="Signals by owner"
          subtitle="Each call counts once, under the owner of its most serious finding."
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
              <Note>
                {/* Counted from the bars rather than stated, so the sentence cannot
                    drift from the chart above it as the corpus changes. */}
                <b>{ownerTotal(signals.data.owners)}</b> of {metrics.total_calls} calls raise at
                least one signal; the rest raise none. A call raising findings for two teams is
                counted for the team owning the more serious one, so no call appears twice.
                Owners with no signals are shown so the absence is visible rather than implied.
              </Note>
            </>
          ) : null}
        </Card>
      </div>

      <div className={styles.eyebrow}>What the time bought</div>
      <Card
        title="Productive and unproductive minutes"
        subtitle="Counted in minutes, not calls — the hours a resolution cost, and the hours that bought none."
      >
        <TimeValueCard />
      </Card>
    </>
  )
}
