import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryUnderstanding } from '@/components/QueryUnderstanding'

describe('QueryUnderstanding', () => {
  it('shows keywords and inferred filters when the LLM was used', () => {
    render(
      <QueryUnderstanding
        understanding={{
          used_llm: true,
          keywords: 'black leather jacket',
          inferred_filters: { gender: 'Men', color: 'Black' },
          fallback_reason: null,
        }}
      />
    )
    expect(screen.getByText('“black leather jacket”')).toBeInTheDocument()
    expect(screen.getByText('Gender: Men')).toBeInTheDocument()
    expect(screen.getByText('Color: Black')).toBeInTheDocument()
  })

  it('explains a non-English query that skipped the LLM', () => {
    render(
      <QueryUnderstanding
        understanding={{
          used_llm: false,
          keywords: null,
          inferred_filters: {},
          fallback_reason: 'unsupported_query',
        }}
      />
    )
    expect(screen.getByText(/Non-English query/)).toBeInTheDocument()
  })

  it('explains when the LLM was unavailable', () => {
    render(
      <QueryUnderstanding
        understanding={{
          used_llm: false,
          keywords: null,
          inferred_filters: {},
          fallback_reason: 'llm_unavailable',
        }}
      />
    )
    expect(screen.getByText(/LLM unavailable/)).toBeInTheDocument()
  })

  it('renders nothing when query understanding is disabled', () => {
    const { container } = render(<QueryUnderstanding understanding={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
