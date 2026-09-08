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

import { useState } from 'react'
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

export interface TimeSeriesPoint {
  readonly label: string
  /** `null` where the week measured nothing — breaks the line rather than
   *  interpolating across it. */
  readonly quality: number | null
  readonly ahtMinutes: number | null
}

const QUALITY_TICKS = [100, 75, 50, 25, 0]
const AHT_TICK_COUNT = 5

/** Padding keeps the highest and lowest weeks off the right axis's own edge. */
const AHT_AXIS_PADDING = 0.12

const SERIES_COLOURS = { quality: '#B26A00', aht: '#14514F' } as const

/** Splits a series into runs of consecutive measured points, so a week that
 *  measured nothing breaks the line instead of being interpolated through. */
function runs(xs: readonly number[], ys: readonly (number | null)[]): { x: number; y: number }[][] {
  const result: { x: number; y: number }[][] = []
  let run: { x: number; y: number }[] = []
  for (const [index, y] of ys.entries()) {
    if (y === null) {
      if (run.length > 0) result.push(run)
      run = []
    } else {
      const x = xs[index]
      if (x !== undefined) run.push({ x, y })
    }
  }
  if (run.length > 0) result.push(run)
  return result
}

/**
 * Overall Call Quality and Average Handling Time, one line each, over time.
 *
 * The two are on different scales — a score out of 100 and a duration in
 * minutes — so they read against their own axis: quality fixed to the 0–100
 * box every score on this dashboard uses, handling time scaled to the weeks
 * actually on the plot. A week that measured neither is a gap in both lines,
 * not a guess at zero.
 */
export function DualLineTrend({
  points,
  height = 220,
}: {
  points: readonly TimeSeriesPoint[]
  height?: number
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)

  if (points.length === 0) {
    return <p className={styles.faint}>No week in this window measured either figure.</p>
  }

  const minutesValues = points
    .map((point) => point.ahtMinutes)
    .filter((value): value is number => value !== null)

  if (minutesValues.length === 0) {
    return <p className={styles.faint}>No week in this window measured either figure.</p>
  }

  const rawMin = Math.min(...minutesValues)
  const rawMax = Math.max(...minutesValues)
  const pad = (rawMax - rawMin || rawMax || 1) * AHT_AXIS_PADDING
  const domainMin = Math.max(0, rawMin - pad)
  const domainMax = rawMax + pad
  const domainSpan = domainMax - domainMin || 1

  const width = 100
  const step = points.length > 1 ? width / (points.length - 1) : 0
  const xs = points.map((_, index) => (points.length > 1 ? index * step : width / 2))

  const qualityY = points.map((point) => (point.quality === null ? null : 100 - point.quality))
  const ahtY = points.map((point) =>
    point.ahtMinutes === null ? null : 100 - ((point.ahtMinutes - domainMin) / domainSpan) * 100,
  )

  const ahtTicks = Array.from({ length: AHT_TICK_COUNT }, (_, index) =>
    (domainMax - (domainSpan * index) / (AHT_TICK_COUNT - 1)).toFixed(1),
  )

  const active = activeIndex === null ? null : points[activeIndex]
  const clear = () => {
    setActiveIndex(null)
  }

  return (
    <div className={styles.trend}>
      <div className={cx(styles.legend, styles.legendRight)}>
        <span className={styles.legendItem}>
          <span className={styles.swatch} style={{ background: SERIES_COLOURS.quality }} />
          Overall Call Quality
        </span>
        <span className={styles.legendItem}>
          <span className={styles.swatch} style={{ background: SERIES_COLOURS.aht }} />
          Average Handling Time
        </span>
      </div>

      <div className={styles.plotRow}>
        <div className={styles.axisY} style={{ height }}>
          {QUALITY_TICKS.map((tick) => (
            <span key={tick}>{tick}</span>
          ))}
        </div>
        <div className={styles.scatterArea} style={{ height }}>
          <svg
            className={styles.trendPlot}
            viewBox={`0 0 ${String(width)} 100`}
            preserveAspectRatio="none"
            style={{ height }}
            role="img"
            aria-label="Overall Call Quality and Average Handling Time, week by week"
          >
            {QUALITY_TICKS.map((tick) => (
              <line
                key={tick}
                x1="0"
                x2={width}
                y1={100 - tick}
                y2={100 - tick}
                className={styles.trendRule}
              />
            ))}
            {xs.map((x, index) => (
              <rect
                key={points[index]?.label ?? index}
                className={styles.hoverColumn}
                x={x - step / 2}
                y="0"
                width={step || width}
                height="100"
                tabIndex={0}
                role="img"
                aria-label={hoverLabel(points[index])}
                onMouseEnter={() => {
                  setActiveIndex(index)
                }}
                onFocus={() => {
                  setActiveIndex(index)
                }}
                onMouseLeave={clear}
                onBlur={clear}
              />
            ))}
            {runs(xs, qualityY).map((segment) => (
              <polyline
                key={`quality-${String(segment[0]?.x ?? 0)}`}
                className={styles.trendLine}
                stroke={SERIES_COLOURS.quality}
                points={segment.map((p) => `${String(p.x)},${String(p.y)}`).join(' ')}
              />
            ))}
            {runs(xs, ahtY).map((segment) => (
              <polyline
                key={`aht-${String(segment[0]?.x ?? 0)}`}
                className={styles.trendLine}
                stroke={SERIES_COLOURS.aht}
                points={segment.map((p) => `${String(p.x)},${String(p.y)}`).join(' ')}
              />
            ))}
          </svg>
          {/* Plain HTML dots, positioned by the same percentages as the SVG
              points, rather than SVG `<circle>` elements: the plot's box is
              far wider than it is tall, and a shape stretched by that much
              turns a circle into an ellipse. A circle sized in CSS pixels
              stays a circle whatever the box's aspect ratio is. */}
          {xs.map((x, index) => {
            const y = qualityY[index]
            if (y === undefined || y === null) return null
            return (
              <span
                key={`quality-point-${points[index]?.label ?? String(index)}`}
                className={cx(styles.point, index === activeIndex && styles.pointActive)}
                style={{ left: `${String(x)}%`, top: `${String(y)}%`, background: SERIES_COLOURS.quality }}
                aria-hidden="true"
              />
            )
          })}
          {xs.map((x, index) => {
            const y = ahtY[index]
            if (y === undefined || y === null) return null
            return (
              <span
                key={`aht-point-${points[index]?.label ?? String(index)}`}
                className={cx(styles.point, index === activeIndex && styles.pointActive)}
                style={{ left: `${String(x)}%`, top: `${String(y)}%`, background: SERIES_COLOURS.aht }}
                aria-hidden="true"
              />
            )
          })}
          {active ? (
            <div
              className={styles.scatterTooltip}
              style={{ left: `${String(xs[activeIndex ?? 0])}%`, top: '0%' }}
            >
              <b>{active.label}</b>
              <span>Quality {active.quality ?? '—'}</span>
              <span>AHT {active.ahtMinutes ?? '—'}m</span>
            </div>
          ) : null}
        </div>
        <div className={styles.axisY} style={{ height }}>
          {ahtTicks.map((tick, index) => (
            // Ticks can repeat when the window's handling time barely moves;
            // the index keeps each one distinct without implying a real key.
            <span key={`${tick}-${String(index)}`}>{tick}m</span>
          ))}
        </div>
      </div>

      <div className={styles.plotRow}>
        <div className={styles.axisYSpacer} />
        <div className={styles.axisX}>
          {points.map((point) => (
            <span key={point.label}>{point.label}</span>
          ))}
        </div>
        <div className={styles.axisYSpacer} />
      </div>
    </div>
  )
}

function hoverLabel(point: TimeSeriesPoint | undefined): string {
  if (!point) return ''
  const quality = point.quality === null ? 'no quality figure' : `quality ${String(point.quality)}`
  const aht =
    point.ahtMinutes === null
      ? 'no handling time figure'
      : `average handling time ${String(point.ahtMinutes)} minutes`
  return `${point.label}: ${quality}, ${aht}`
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
