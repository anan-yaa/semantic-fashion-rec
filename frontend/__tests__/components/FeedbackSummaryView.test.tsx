import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FeedbackSummaryView } from '@/components/FeedbackSummaryView'
import { FeedbackSummary } from '@/types/feedback'

const empty: FeedbackSummary = {
  total_votes: 0, helpful: 0, not_helpful: 0, helpful_rate: null, queries: 0, clients: 0,
  most_not_helpful: [], recent: [],
}

describe('FeedbackSummaryView', () => {
  it('explains how to give feedback when there is none', () => {
    render(<FeedbackSummaryView summary={empty} />)
    expect(screen.getByText('No feedback yet')).toBeInTheDocument()
  })

  it('shows totals, worst queries and recent votes', () => {
    render(
      <FeedbackSummaryView
        summary={{
          total_votes: 5, helpful: 2, not_helpful: 3, helpful_rate: 0.4, queries: 3, clients: 2,
          most_not_helpful: [{ query: 'red dress', helpful: 1, not_helpful: 2 }],
          recent: [{ query: 'black jacket', product_id: 'p3', product_name: 'Black Jacket', vote: 1, position: 4,
                     llm_used: true, updated_at: '2026-10-06T10:00:00Z' }],
        }}
      />
    )
    expect(screen.getByText('40%')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'red dress' })).toHaveAttribute('href', '/?q=red%20dress')
    expect(screen.getByRole('listitem')).toHaveTextContent('Black Jacket for “black jacket”')
    expect(screen.getByText('#4')).toBeInTheDocument()
  })
})
