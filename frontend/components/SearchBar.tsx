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
    <form
      onSubmit={handleSubmit}
      role="search"
      className="flex items-center gap-2 bg-white border border-border rounded-full shadow-sm pl-5 pr-2 py-2 focus-within:ring-2 focus-within:ring-primary/80 focus-within:border-transparent transition"
    >
      <svg
        className="h-5 w-5 shrink-0 text-muted"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" strokeLinecap="round" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search for fashion in your own words…"
        aria-label="Search query"
        className="flex-1 min-w-0 bg-transparent py-2 text-base placeholder:text-muted focus:outline-none disabled:opacity-60"
        disabled={isLoading}
      />
      {value && !isLoading && (
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear"
          className="h-8 w-8 shrink-0 flex items-center justify-center rounded-full text-secondary hover:bg-hover transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
          </svg>
        </button>
      )}
      <button
        type="submit"
        disabled={isLoading || !value.trim()}
        className="shrink-0 flex items-center gap-2 px-5 py-2.5 bg-primary text-white text-sm font-medium rounded-full hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading && (
          <span className="h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin" aria-hidden="true" />
        )}
        {isLoading ? 'Searching' : 'Search'}
      </button>
    </form>
  )
}
