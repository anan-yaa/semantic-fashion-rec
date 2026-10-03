import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '@/components/Pagination'

describe('Pagination', () => {
  it('returns null when totalPages is 1', () => {
    const mockOnPageChange = vi.fn()
    const { container } = render(
      <Pagination page={1} totalPages={1} onPageChange={mockOnPageChange} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders page information', () => {
    const mockOnPageChange = vi.fn()
    render(<Pagination page={2} totalPages={5} onPageChange={mockOnPageChange} />)
    // "Page 2 of 5" is split across <strong> tags, so match on textContent
    // of the containing element rather than a single text node.
    expect(
      screen.getByText((_, element) => element?.textContent === 'Page 2 of 5')
    ).toBeInTheDocument()
  })

  it('disables Previous button on first page', () => {
    const mockOnPageChange = vi.fn()
    render(<Pagination page={1} totalPages={5} onPageChange={mockOnPageChange} />)
    const prevButton = screen.getByRole('button', { name: /Previous/i })
    expect(prevButton).toBeDisabled()
  })

  it('disables Next button on last page', () => {
    const mockOnPageChange = vi.fn()
    render(<Pagination page={5} totalPages={5} onPageChange={mockOnPageChange} />)
    const nextButton = screen.getByRole('button', { name: /Next/i })
    expect(nextButton).toBeDisabled()
  })

  it('calls onPageChange with correct page when Previous is clicked', () => {
    const mockOnPageChange = vi.fn()
    render(<Pagination page={3} totalPages={5} onPageChange={mockOnPageChange} />)
    const prevButton = screen.getByRole('button', { name: /Previous/i })
    fireEvent.click(prevButton)
    expect(mockOnPageChange).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange with correct page when Next is clicked', () => {
    const mockOnPageChange = vi.fn()
    render(<Pagination page={2} totalPages={5} onPageChange={mockOnPageChange} />)
    const nextButton = screen.getByRole('button', { name: /Next/i })
    fireEvent.click(nextButton)
    expect(mockOnPageChange).toHaveBeenCalledWith(3)
  })
})
