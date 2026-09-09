import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  Bar,
  DeltaMetric,
  DualLineTrend,
  Histogram,
  Legend,
  Metric,
  MetricStrip,
} from '@/shared/ui/charts'
import chartStyles from '@/shared/ui/charts.module.css'

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

describe('DualLineTrend', () => {
  const points = [
    { label: '31 Aug', quality: 79, ahtMinutes: 6.2 },
    { label: '7 Sep', quality: 78, ahtMinutes: 7.5 },
    { label: '14 Sep', quality: null, ahtMinutes: null },
    { label: '21 Sep', quality: 69.5, ahtMinutes: 8.1 },
  ]

  it('labels the quality scale so a fall can be sized', () => {
    render(<DualLineTrend points={points} />)

    for (const tick of ['0', '25', '50', '75', '100']) {
      expect(screen.getByText(tick)).toBeInTheDocument()
    }
  })

  it('labels the handling-time scale against the weeks actually plotted', () => {
    render(<DualLineTrend points={points} />)

    // Padded a little past the 6.2-8.1 range the fixture spans.
    expect(screen.getByText(/^8\.\dm$/)).toBeInTheDocument()
    expect(screen.getByText(/^6\.0m$/)).toBeInTheDocument()
  })

  it('draws one point per week that measured that figure', () => {
    // Three weeks have a quality figure, three have a handling-time figure —
    // the unmeasured week (14 Sep) contributes to neither.
    const { container } = render(<DualLineTrend points={points} />)

    expect(container.getElementsByClassName((chartStyles.point ?? ''))).toHaveLength(6)
  })

  it('breaks each line where a week measured nothing', () => {
    // Two lines, each broken into two runs by the unmeasured week: four
    // polylines in total, not two drawn straight through the gap.
    const { container } = render(<DualLineTrend points={points} />)

    expect(container.querySelectorAll('polyline')).toHaveLength(4)
  })

  it("shows a week's numbers on hover", async () => {
    const user = userEvent.setup()
    render(<DualLineTrend points={points} />)

    const column = screen.getByRole('img', { name: /31 Aug/ })
    await user.hover(column)

    expect(screen.getByText('Quality 79')).toBeInTheDocument()
    expect(screen.getByText('AHT 6.2m')).toBeInTheDocument()
  })

  it("shows a week's numbers on keyboard focus, not only on hover", async () => {
    const user = userEvent.setup()
    render(<DualLineTrend points={points} />)

    await user.tab()
    expect(screen.getByText('Quality 79')).toBeInTheDocument()
  })

  it('names every week along the horizontal axis', () => {
    render(<DualLineTrend points={points} />)

    for (const label of ['31 Aug', '7 Sep', '14 Sep', '21 Sep']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
  })

  it('says so rather than drawing a plot with nothing measured', () => {
    render(<DualLineTrend points={[{ label: '31 Aug', quality: null, ahtMinutes: null }]} />)

    expect(screen.getByText(/No week in this window measured either figure/)).toBeInTheDocument()
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

    expect(screen.getByText(/▼ 23.8 pts from last week/)).toBeInTheDocument()
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
