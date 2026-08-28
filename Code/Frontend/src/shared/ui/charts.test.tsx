import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Bar, Histogram, Legend, Metric, MetricStrip } from '@/shared/ui/charts'

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
