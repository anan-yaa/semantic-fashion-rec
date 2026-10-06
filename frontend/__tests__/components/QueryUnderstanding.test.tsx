import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryUnderstanding } from '@/components/QueryUnderstanding'

const base = { used_llm: true, translated: false, english_query: null, inferred_filters: {}, fallback_reason: null }

describe('QueryUnderstanding', () => {
  it('shows inferred filters for an English query', () => {
    render(<QueryUnderstanding understanding={{ ...base, inferred_filters: { gender: 'Men', color: 'Black' } }} />)
    expect(screen.getByText('Understood as:')).toBeInTheDocument()
    expect(screen.getByText('Gender: Men')).toBeInTheDocument()
    expect(screen.getByText('Color: Black')).toBeInTheDocument()
  })

  it('shows the English translation a non-English query was searched with', () => {
    render(
      <QueryUnderstanding
        understanding={{ ...base, translated: true, english_query: 'red saree', inferred_filters: { color: 'Red' } }}
      />
    )
    expect(screen.getByText('Searched in English as:')).toBeInTheDocument()
    expect(screen.getByText('“red saree”')).toBeInTheDocument()
    expect(screen.getByText('Color: Red')).toBeInTheDocument()
  })

  it('shows nothing when the LLM found nothing to add', () => {
    const { container } = render(<QueryUnderstanding understanding={base} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('explains a non-English query that skipped the LLM', () => {
    render(<QueryUnderstanding understanding={{ ...base, used_llm: false, fallback_reason: 'unsupported_query' }} />)
    expect(screen.getByText(/Non-English query/)).toBeInTheDocument()
  })

  it('explains when the LLM was unavailable', () => {
    render(<QueryUnderstanding understanding={{ ...base, used_llm: false, fallback_reason: 'llm_unavailable' }} />)
    expect(screen.getByText(/LLM unavailable/)).toBeInTheDocument()
  })

  it('renders nothing when query understanding is disabled', () => {
    const { container } = render(<QueryUnderstanding understanding={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
