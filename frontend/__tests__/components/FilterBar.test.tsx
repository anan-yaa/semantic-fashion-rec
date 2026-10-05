import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterBar } from '@/components/FilterBar'
import { Facets } from '@/types/product'

const facets: Facets = {
  category: ['Apparel', 'Footwear'],
  gender: ['Men', 'Women'],
  color: ['Black', 'Red'],
  season: ['Summer', 'Winter'],
}

function renderBar(overrides: Partial<Parameters<typeof FilterBar>[0]> = {}) {
  const props = {
    facets,
    filters: {},
    sort: 'relevance' as const,
    onFiltersChange: vi.fn(),
    onSortChange: vi.fn(),
    mode: 'search' as const,
    ...overrides,
  }
  render(<FilterBar {...props} />)
  return props
}

describe('FilterBar', () => {
  it('lists catalogue values for each filter', () => {
    renderBar()
    expect(screen.getByRole('option', { name: 'Footwear' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Women' })).toBeInTheDocument()
  })

  it('sets a filter', () => {
    const props = renderBar({ filters: { season: 'Summer' } })
    fireEvent.change(screen.getByLabelText('Color'), { target: { value: 'Red' } })
    expect(props.onFiltersChange).toHaveBeenCalledWith({ season: 'Summer', color: 'Red' })
  })

  it('removes a filter when set back to All', () => {
    const props = renderBar({ filters: { color: 'Red', gender: 'Men' } })
    fireEvent.change(screen.getByLabelText('Color'), { target: { value: '' } })
    expect(props.onFiltersChange).toHaveBeenCalledWith({ gender: 'Men' })
  })

  it('clears all filters', () => {
    const props = renderBar({ filters: { color: 'Red', gender: 'Men' } })
    fireEvent.click(screen.getByRole('button', { name: /Clear filters \(2\)/ }))
    expect(props.onFiltersChange).toHaveBeenCalledWith({})
  })

  it('hides clear when no filters are set', () => {
    renderBar()
    expect(screen.queryByRole('button', { name: /Clear filters/ })).not.toBeInTheDocument()
  })

  it('changes sort', () => {
    const props = renderBar()
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'newest' } })
    expect(props.onSortChange).toHaveBeenCalledWith('newest')
  })

  it('labels relevance as Featured when browsing', () => {
    renderBar({ mode: 'browse' })
    expect(screen.getByRole('option', { name: 'Featured' })).toBeInTheDocument()
  })

  it('disables filters until facets load', () => {
    renderBar({ facets: null })
    expect(screen.getByLabelText('Gender')).toBeDisabled()
  })
})
