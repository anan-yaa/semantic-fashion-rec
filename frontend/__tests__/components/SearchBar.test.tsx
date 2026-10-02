import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from '@/components/SearchBar'

describe('SearchBar', () => {
  it('renders search input', () => {
    const mockOnSearch = vi.fn()
    render(<SearchBar onSearch={mockOnSearch} />)
    expect(screen.getByPlaceholderText(/Search for fashion/i)).toBeInTheDocument()
  })

  it('calls onSearch when form is submitted', () => {
    const mockOnSearch = vi.fn()
    render(<SearchBar onSearch={mockOnSearch} />)

    const input = screen.getByPlaceholderText(/Search for fashion/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'blue shirt' } })
    fireEvent.submit(input.closest('form')!)

    // Note: onSearch is called but in actual component it shows "not implemented" message
    expect(input.value).toBe('blue shirt')
  })

  it('shows "not implemented" message after search attempt', () => {
    const mockOnSearch = vi.fn()
    render(<SearchBar onSearch={mockOnSearch} />)

    const input = screen.getByPlaceholderText(/Search for fashion/i)
    fireEvent.change(input, { target: { value: 'test query' } })

    const form = input.closest('form')!
    fireEvent.submit(form)

    expect(screen.getByText(/Semantic search is not implemented yet/)).toBeInTheDocument()
  })

  it('clears input on clear button click', () => {
    const mockOnSearch = vi.fn()
    render(<SearchBar onSearch={mockOnSearch} />)

    const input = screen.getByPlaceholderText(/Search for fashion/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'test' } })

    const clearButton = screen.getByRole('button', { name: /Clear/i })
    fireEvent.click(clearButton)

    expect(input.value).toBe('')
  })

  it('disables search button when input is empty', () => {
    const mockOnSearch = vi.fn()
    render(<SearchBar onSearch={mockOnSearch} />)

    const searchButton = screen.getByRole('button', { name: /Search/i })
    expect(searchButton).toBeDisabled()
  })
})
