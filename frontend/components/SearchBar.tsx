/**
 * SearchBar: Search input component
 * Accepts user query but shows "not implemented" for semantic search
 */

'use client'

import { useState } from 'react'

interface SearchBarProps {
  onSearch?: (query: string) => void
  isLoading?: boolean
}

export function SearchBar({ isLoading = false }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [showNotImplemented, setShowNotImplemented] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      setShowNotImplemented(true)
    }
  }

  const handleClear = () => {
    setQuery('')
    setShowNotImplemented(false)
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for fashion products..."
          className="flex-1 px-4 py-3 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="px-6 py-3 bg-primary text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Search
        </button>
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="px-6 py-3 border border-border rounded-lg hover:bg-hover transition-colors"
          >
            Clear
          </button>
        )}
      </form>

      {showNotImplemented && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm">
          <p className="text-blue-900">
            <strong>Semantic search is not implemented yet.</strong> This interface will use the
            search API once Day 2 is complete. For now, you can browse the full catalogue below.
          </p>
        </div>
      )}
    </div>
  )
}
