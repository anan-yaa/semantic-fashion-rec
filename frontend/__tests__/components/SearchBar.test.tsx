import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from '@/components/SearchBar'

function renderSearchBar(overrides: Partial<Parameters<typeof SearchBar>[0]> = {}) {
  const props = {
    value: '',
    onChange: vi.fn(),
    onSubmit: vi.fn(),
    onClear: vi.fn(),
    ...overrides,
  }
  render(<SearchBar {...props} />)
  return props
}

describe('SearchBar', () => {
  it('renders search input', () => {
    renderSearchBar()
    expect(screen.getByPlaceholderText(/Search for fashion/i)).toBeInTheDocument()
  })

  it('reflects the controlled value prop', () => {
    renderSearchBar({ value: 'blue shirt' })
    const input = screen.getByPlaceholderText(/Search for fashion/i) as HTMLInputElement
    expect(input.value).toBe('blue shirt')
  })

  it('calls onChange as the user types', () => {
    const props = renderSearchBar()
    const input = screen.getByPlaceholderText(/Search for fashion/i)
    fireEvent.change(input, { target: { value: 'blue shirt' } })
    expect(props.onChange).toHaveBeenCalledWith('blue shirt')
  })

  it('calls onSubmit with the trimmed query when the form is submitted', () => {
    const props = renderSearchBar({ value: '  blue shirt  ' })
    const form = screen.getByPlaceholderText(/Search for fashion/i).closest('form')!
    fireEvent.submit(form)
    expect(props.onSubmit).toHaveBeenCalledWith('blue shirt')
  })

  it('does not call onSubmit for an empty/whitespace-only query', () => {
    const props = renderSearchBar({ value: '   ' })
    const form = screen.getByPlaceholderText(/Search for fashion/i).closest('form')!
    fireEvent.submit(form)
    expect(props.onSubmit).not.toHaveBeenCalled()
  })

  it('calls onClear when the clear button is clicked', () => {
    const props = renderSearchBar({ value: 'blue shirt' })
    const clearButton = screen.getByRole('button', { name: /Clear/i })
    fireEvent.click(clearButton)
    expect(props.onClear).toHaveBeenCalled()
  })

  it('does not render the clear button when value is empty', () => {
    renderSearchBar({ value: '' })
    expect(screen.queryByRole('button', { name: /Clear/i })).not.toBeInTheDocument()
  })

  it('disables search button when input is empty', () => {
    renderSearchBar({ value: '' })
    const searchButton = screen.getByRole('button', { name: /Search/i })
    expect(searchButton).toBeDisabled()
  })

  it('disables input and search button while isLoading', () => {
    renderSearchBar({ value: 'blue shirt', isLoading: true })
    expect(screen.getByPlaceholderText(/Search for fashion/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /Search/i })).toBeDisabled()
  })
})
