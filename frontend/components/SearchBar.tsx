/**
 * SearchBar: Controlled search input wired to POST /search
 */

'use client'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  onSubmit: (query: string) => void
  onClear: () => void
  isLoading?: boolean
}

export function SearchBar({ value, onChange, onSubmit, onClear, isLoading = false }: SearchBarProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim()) {
      onSubmit(value.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search for fashion products..."
        className="flex-1 px-4 py-3 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !value.trim()}
        className="px-6 py-3 bg-primary text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Search
      </button>
      {value && (
        <button
          type="button"
          onClick={onClear}
          className="px-6 py-3 border border-border rounded-lg hover:bg-hover transition-colors"
        >
          Clear
        </button>
      )}
    </form>
  )
}
