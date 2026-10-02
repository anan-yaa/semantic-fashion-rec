/**
 * SearchExamples: Suggestions for search queries
 */

const EXAMPLE_QUERIES = [
  'I need a comfortable outfit for the beach this summer',
  'Show me casual clothes for men',
  'I want something red for summer',
  'Traditional clothing for women',
]

interface SearchExamplesProps {
  onSelect: (query: string) => void
}

export function SearchExamples({ onSelect }: SearchExamplesProps) {
  return (
    <div className="mt-4">
      <p className="text-sm text-secondary mb-3">Example queries (semantic search coming soon):</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {EXAMPLE_QUERIES.map((query) => (
          <button
            key={query}
            onClick={() => onSelect(query)}
            className="text-left text-sm px-3 py-2 border border-border rounded-lg hover:bg-hover transition-colors"
          >
            {query}
          </button>
        ))}
      </div>
    </div>
  )
}
