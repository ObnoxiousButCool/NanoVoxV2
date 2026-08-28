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

import { Link } from 'react-router-dom'

import { useAgents, useOverview, useSignals } from '@/shared/api/queries'
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

function ResolutionByAgent({ agents }: { agents: readonly AgentPerformance[] }) {
  if (agents.length === 0) {
    return <Note>No agents have been named in an analysed call yet.</Note>
  }

  return (
    <>
      <BarRows>
        {agents.map((agent) => (
          <Bar
            key={agent.agent_name}
            label={`${agent.agent_name} · ${String(agent.call_count)}`}
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
            bars={histogram.bins.map((bin) => ({
              label: bin.label,
              count: bin.count,
              isBelowThreshold: bin.is_below_threshold,
            }))}
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
          subtitle="A call can raise more than one signal, so these do not total the call count."
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
                Owners with no signals are shown so the absence is visible rather than implied.
              </Note>
            </>
          ) : null}
        </Card>
      </div>
    </>
  )
}
