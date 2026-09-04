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

export interface TrendSeries {
  readonly label: string
  readonly color: string
  /** One value per point, `null` where the period measured nothing. */
  readonly values: readonly (number | null)[]
  /** Axis ceiling. Fixed per series so two series can share one plot. */
  readonly max: number
  readonly format: (value: number) => string
}

/**
 * A weekly series, drawn as a line per measure.
 *
 * Two measures on different scales share one plot — a score out of 100 and a
 * percentage — because the question is whether they move together, and two
 * stacked charts make that comparison an act of memory. Each series carries its
 * own ceiling and is drawn to the same box, so the shapes are comparable while
 * the values stay in their own units.
 *
 * A period that measured nothing breaks the line rather than interpolating
 * across it. A straight segment through a week nobody called would draw a
 * measurement that was never taken.
 */
export function TrendLine({
  series,
  labels,
  height = 150,
}: {
  series: readonly TrendSeries[]
  labels: readonly string[]
  height?: number
}) {
  const width = 100
  const step = labels.length > 1 ? width / (labels.length - 1) : 0
  // Every series here is drawn to the same ceiling, so one axis describes them
  // all. Ticks are the reader's only way to tell a fall of four points from a
  // fall of forty — the line shape alone is the same either way.
  const ceiling = Math.max(...series.map((line) => line.max))
  const ticks = [100, 75, 50, 25, 0].map((share) => Math.round((ceiling * share) / 100))

  return (
    <div className={styles.trend}>
      <div className={styles.legend}>
        {series.map((line) => (
          <span key={line.label} className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: line.color }} />
            {line.label}
          </span>
        ))}
      </div>

      <div className={styles.plotRow}>
        <div className={styles.axisY} style={{ height }}>
          {ticks.map((tick) => (
            <span key={tick}>{tick}</span>
          ))}
        </div>
      <svg
        className={styles.trendPlot}
        viewBox={`0 0 ${String(width)} 100`}
        preserveAspectRatio="none"
        style={{ height }}
        role="img"
        aria-label={`Weekly trend: ${series.map((line) => line.label).join(', ')}`}
      >
        {[0, 25, 50, 75, 100].map((y) => (
          <line key={y} x1="0" x2={width} y1={y} y2={y} className={styles.trendRule} />
        ))}
        {series.map((line) => {
          const points = line.values.map((value, index) => ({
            x: labels.length > 1 ? index * step : width / 2,
            y: value === null ? null : 100 - (Math.min(value, line.max) * 100) / line.max,
          }))

          // Split into runs of consecutive measured points, so a gap stays a gap.
          const runs: { x: number; y: number }[][] = []
          let run: { x: number; y: number }[] = []
          for (const point of points) {
            if (point.y === null) {
              if (run.length > 0) runs.push(run)
              run = []
            } else {
              run.push({ x: point.x, y: point.y })
            }
          }
          if (run.length > 0) runs.push(run)

          return (
            <g key={line.label}>
              {runs.map((segment) => (
                <polyline
                  key={`${line.label}-${String(segment[0]?.x ?? 0)}`}
                  className={styles.trendLine}
                  stroke={line.color}
                  points={segment.map((p) => `${String(p.x)},${String(p.y)}`).join(' ')}
                />
              ))}
            </g>
          )
        })}
      </svg>
      </div>

      <div className={styles.plotRow}>
        <div className={styles.axisYSpacer} />
        <div className={styles.trendAxis}>
          {labels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      </div>
      <div className={styles.axisNote}>
        Week beginning, left to right. Both series read against the same 0–{ceiling} scale.
      </div>

      <div className={styles.dataScroll}>
      <table className={styles.dataTable}>
        <caption className={styles.visuallyHidden}>The weekly series, as values</caption>
        <thead>
          <tr>
            <th scope="col">Week</th>
            {series.map((line) => (
              <th key={line.label} scope="col">
                <span className={styles.swatch} style={{ background: line.color }} />
                {line.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, index) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              {series.map((line) => {
                const value = line.values[index]
                return (
                  <td key={line.label}>
                    {value === null || value === undefined ? '—' : line.format(value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  )
}

/**
 * A metric with its move since the previous period.
 *
 * The direction that reads as good differs by measure — resolution rising is
 * good, handle time rising is not necessarily anything — so the caller states
 * which way is up rather than the component assuming bigger is better.
 */
export function DeltaMetric({
  label,
  value,
  delta,
  format,
  goodDirection = 'up',
  sub,
}: {
  label: string
  value: ReactNode
  delta: number | null | undefined
  format: (value: number) => string
  goodDirection?: 'up' | 'down' | 'neutral'
  sub?: ReactNode
}) {
  const flat = delta === null || delta === undefined || delta === 0
  const tone = flat || goodDirection === 'neutral'
    ? styles.deltaFlat
    : (delta > 0) === (goodDirection === 'up')
      ? styles.deltaGood
      : styles.deltaBad

  return (
    <div className={styles.metric}>
      <div className={styles.metricKey}>{label}</div>
      <div className={styles.metricValue}>{value}</div>
      <div className={styles.metricSub}>
        {delta === null || delta === undefined ? (
          <span className={styles.deltaFlat}>No previous week</span>
        ) : (
          <span className={tone}>
            {delta > 0 ? '▲' : delta < 0 ? '▼' : '■'} {format(Math.abs(delta))} on last week
          </span>
        )}
        {sub === undefined ? null : <div>{sub}</div>}
      </div>
    </div>
  )
}
