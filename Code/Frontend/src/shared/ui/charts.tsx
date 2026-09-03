/**
 * Charts, drawn with CSS rather than a charting library (plan A2).
 *
 * The prototype's bars and histogram are already CSS; a library would fight the
 * design for no gain and add a dependency to maintain.
 *
 * One rule runs through all of them: **a zero is drawn, not omitted.** An absent
 * bar reads as though the category does not exist, which is exactly the
 * misreading the dashboard is meant to prevent.
 */

import type { ReactNode } from 'react'

import { cx } from '@/shared/ui/cx'
import styles from './charts.module.css'

export interface BarSegment {
  readonly value: number
  readonly color: string
  readonly label: string
}

function widths(segments: readonly BarSegment[]): number[] {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0)
  if (total <= 0) {
    return segments.map(() => 0)
  }
  return segments.map((segment) => (segment.value * 100) / total)
}

/**
 * One labelled bar. Segments are drawn proportionally, so agents with different
 * call volumes stay comparable — the count is shown separately.
 */
export function Bar({
  label,
  segments,
  value,
  title,
}: {
  // A node, not just a string, so a caller can make the label a link without
  // this module having to know about routing.
  label: ReactNode
  segments: readonly BarSegment[]
  value: ReactNode
  title?: string | undefined
}) {
  const percentages = widths(segments)

  return (
    <div className={styles.row}>
      <span
        className={styles.label}
        title={title ?? (typeof label === 'string' ? label : undefined)}
      >
        {label}
      </span>
      <span className={styles.track}>
        {segments.map((segment, index) => (
          <i
            key={segment.label}
            className={styles.segment}
            style={{ width: `${String(percentages[index] ?? 0)}%`, background: segment.color }}
            title={`${segment.label}: ${String(segment.value)}`}
          />
        ))}
      </span>
      <span className={styles.value}>{value}</span>
    </div>
  )
}

export function BarRows({ children }: { children: ReactNode }) {
  return <div className={styles.rows}>{children}</div>
}

export function Legend({ items }: { items: readonly { label: string; color: string }[] }) {
  return (
    <div className={styles.legend}>
      {items.map((item) => (
        <span key={item.label}>
          <b className={styles.swatch} style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  )
}

export interface HistogramBar {
  readonly label: string
  readonly count: number
  readonly isBelowThreshold: boolean
  /** Makes the bar selectable. Omitted, it is drawn as a plain bar. */
  readonly onSelect?: () => void
  /** What selecting it does, for anything that cannot see the chart. */
  readonly selectLabel?: string
}

/**
 * The score distribution.
 *
 * Bars below the coaching threshold are coloured as the population needing
 * intervention — the corpus is bimodal, and the point of the chart is that the
 * mean falls in a gap where no call actually sits.
 */
export function Histogram({ bars, peak }: { bars: readonly HistogramBar[]; peak: number }) {
  const tallest = Math.max(peak, 1)

  return (
    <>
      <div className={styles.hist}>
        {bars.map((bar) => {
          const height = `${String(Math.max((bar.count * 100) / tallest, 2))}%`
          const className = cx(styles.bar, bar.isBelowThreshold && styles.barWarn)
          const title = `${bar.label}: ${String(bar.count)}`
          const body = bar.count > 0 ? <span className={styles.barCount}>{bar.count}</span> : null

          // A button rather than a clickable div: a bar that does something has
          // to be reachable by keyboard and announce what it does. An empty bar
          // stays inert — there is nothing to show.
          if (bar.onSelect && bar.count > 0) {
            return (
              <button
                key={bar.label}
                type="button"
                className={cx(className, styles.barButton)}
                style={{ height }}
                title={title}
                aria-label={bar.selectLabel ?? title}
                onClick={bar.onSelect}
              >
                {body}
              </button>
            )
          }

          return (
            <div key={bar.label} className={className} style={{ height }} title={title}>
              {body}
            </div>
          )
        })}
      </div>
      <div className={styles.histAxis}>
        {bars.map((bar) => (
          <span key={bar.label}>{bar.label}</span>
        ))}
      </div>
    </>
  )
}

export function MetricStrip({ children }: { children: ReactNode }) {
  return <div className={styles.metrics}>{children}</div>
}

export function Metric({
  label,
  value,
  sub,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
}) {
  return (
    <div className={styles.metric}>
      <div className={styles.metricKey}>{label}</div>
      <div className={styles.metricValue}>{value}</div>
      {sub ? <div className={styles.metricSub}>{sub}</div> : null}
    </div>
  )
}
