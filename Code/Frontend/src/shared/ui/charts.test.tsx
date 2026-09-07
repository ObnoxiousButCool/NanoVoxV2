import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  Bar,
  DeltaMetric,
  Histogram,
  Legend,
  Metric,
  MetricStrip,
  TrendLine,
} from '@/shared/ui/charts'

describe('Bar', () => {
  it('sizes segments by share so different call volumes stay comparable', () => {
    const { container } = render(
      <Bar
        label="Sarah"
        value={81}
        segments={[
          { value: 3, color: '#0a0', label: 'Resolved' },
          { value: 1, color: '#a00', label: 'Unresolved' },
        ]}
      />,
    )

    const segments = container.querySelectorAll('i')
    expect(segments[0]).toHaveStyle({ width: '75%' })
    expect(segments[1]).toHaveStyle({ width: '25%' })
  })

  it('draws nothing rather than dividing by zero when an agent has no calls', () => {
    const { container } = render(
      <Bar label="Priya" value="-" segments={[{ value: 0, color: '#0a0', label: 'Resolved' }]} />,
    )

    expect(container.querySelector('i')).toHaveStyle({ width: '0%' })
  })

  it('names the count behind each segment for a reader who cannot see colour', () => {
    render(
      <Bar label="Brad" value={46} segments={[{ value: 2, color: '#a00', label: 'Escalated' }]} />,
    )

    expect(screen.getByTitle('Escalated: 2')).toBeInTheDocument()
  })
})

describe('Histogram', () => {
  it('scales bars against the tallest bin', () => {
    const { container } = render(
      <Histogram
        peak={8}
        bars={[
          { label: '0-20', count: 8, isBelowThreshold: true },
          { label: '20-40', count: 4, isBelowThreshold: true },
        ]}
      />,
    )

    expect(container.querySelector('[title="0-20: 8"]')).toHaveStyle({ height: '100%' })
    expect(container.querySelector('[title="20-40: 4"]')).toHaveStyle({ height: '50%' })
  })

  it('keeps an empty bin visible as a gap in the distribution', () => {
    // A bin with no calls is a finding, not an absence - the corpus is bimodal.
    const { container } = render(
      <Histogram peak={8} bars={[{ label: '60-70', count: 0, isBelowThreshold: false }]} />,
    )

    const bar = container.querySelector('[title="60-70: 0"]')
    expect(bar).toBeInTheDocument()
    expect(bar).toHaveStyle({ height: '2%' })
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('survives a corpus where every bin is empty', () => {
    const { container } = render(
      <Histogram peak={0} bars={[{ label: '0-20', count: 0, isBelowThreshold: true }]} />,
    )

    expect(container.querySelector('[title="0-20: 0"]')).toBeInTheDocument()
  })

  it('labels the axis so a bar can be read without hovering', () => {
    render(<Histogram peak={2} bars={[{ label: '80-90', count: 2, isBelowThreshold: false }]} />)

    expect(screen.getByText('80-90')).toBeInTheDocument()
  })
})

describe('Legend', () => {
  it('names every colour it uses', () => {
    render(
      <Legend
        items={[
          { label: 'Resolved', color: '#0a0' },
          { label: 'Escalated', color: '#a00' },
        ]}
      />,
    )

    expect(screen.getByText('Resolved')).toBeInTheDocument()
    expect(screen.getByText('Escalated')).toBeInTheDocument()
  })
})

describe('Metric', () => {
  it('shows a metric with the context that makes it readable', () => {
    render(
      <MetricStrip>
        <Metric label="Resolution rate" value="41.7%" sub="Industry range 65-75%" />
      </MetricStrip>,
    )

    expect(screen.getByText('Resolution rate')).toBeInTheDocument()
    expect(screen.getByText('41.7%')).toBeInTheDocument()
    expect(screen.getByText('Industry range 65-75%')).toBeInTheDocument()
  })

  it('omits the sub-line when there is no context to add', () => {
    const { container } = render(<Metric label="Calls" value={12} />)

    expect(container.textContent).toBe('Calls12')
  })
})

describe('TrendLine', () => {
  const series = [
    {
      label: 'First Call Resolution (FCR)',
      color: '#14514F',
      values: [87.5, null, 33.3],
      max: 100,
      format: (value: number) => `${String(value)}%`,
    },
  ]

  it('labels the vertical scale so a fall can be sized', () => {
    // Without ticks a reader sees that the line falls and cannot see whether it
    // fell four points or forty, which is the whole question.
    render(<TrendLine series={series} labels={['31 Aug', '7 Sep', '14 Sep']} />)

    for (const tick of ['0', '25', '50', '75', '100']) {
      expect(screen.getByText(tick)).toBeInTheDocument()
    }
  })

  it('names each series beside its colour, above the plot', () => {
    // Colour alone is not a label, and the table is below the fold.
    render(<TrendLine series={series} labels={['31 Aug', '7 Sep', '14 Sep']} />)

    expect(screen.getAllByText('First Call Resolution (FCR)').length).toBeGreaterThan(1)
  })

  it('names every period along the horizontal axis', () => {
    // The labels are the axis now that the caption explaining them is gone, so
    // a period losing its label would leave the plot unreadable.
    render(<TrendLine series={series} labels={['31 Aug', '7 Sep', '14 Sep']} />)

    for (const label of ['31 Aug', '7 Sep', '14 Sep']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
  })

  it('breaks the line where a period measured nothing', () => {
    // Two runs, not one line drawn through the gap: a straight segment across
    // an unmeasured week draws a measurement that was never taken.
    const { container } = render(
      <TrendLine series={series} labels={['31 Aug', '7 Sep', '14 Sep']} />,
    )

    expect(container.querySelectorAll('polyline')).toHaveLength(2)
  })

  it('gives the missing period a dash rather than a zero', () => {
    render(<TrendLine series={series} labels={['31 Aug', '7 Sep', '14 Sep']} />)

    const row = screen.getByRole('row', { name: /7 Sep/ })
    expect(within(row).getByText('—')).toBeInTheDocument()
  })
})

describe('DeltaMetric', () => {
  it('carries the direction in words as well as in colour', () => {
    // The page prints in monochrome and is read by people who cannot separate
    // red from green, so the arrow and the sentence do the work colour does.
    render(
      <DeltaMetric
        label="First Call Resolution (FCR)"
        value="57%"
        delta={-23.8}
        format={(value) => `${String(value)} pts`}
      />,
    )

    expect(screen.getByText(/▼ 23.8 pts on last week/)).toBeInTheDocument()
  })

  it('reads a fall as bad when up is good, and the reverse', () => {
    const { container: falling } = render(
      <DeltaMetric label="A" value="1" delta={-5} format={String} goodDirection="up" />,
    )
    const { container: rising } = render(
      <DeltaMetric label="B" value="1" delta={5} format={String} goodDirection="up" />,
    )

    const bad = falling.querySelector('span')?.className
    const good = rising.querySelector('span')?.className
    expect(bad).not.toEqual(good)
  })

  it('treats a measure with no good direction as neither', () => {
    // Handle time: a shorter call is an answer found faster or a member brushed
    // off, and this figure cannot tell them apart.
    const { container: neutral } = render(
      <DeltaMetric label="A" value="1" delta={-5} format={String} goodDirection="neutral" />,
    )
    const { container: bad } = render(
      <DeltaMetric label="B" value="1" delta={-5} format={String} goodDirection="up" />,
    )

    expect(neutral.querySelector('span')?.className).not.toEqual(
      bad.querySelector('span')?.className,
    )
  })

  it('says there is nothing to compare against rather than showing zero', () => {
    render(<DeltaMetric label="A" value="1" delta={null} format={String} />)

    expect(screen.getByText('No previous week')).toBeInTheDocument()
  })
})
