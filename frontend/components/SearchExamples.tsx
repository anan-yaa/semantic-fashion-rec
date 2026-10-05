/**
 * SearchExamples: Suggested natural-language and multilingual queries
 */

const EXAMPLE_QUERIES = [
  'I need an outfit to go to the beach this summer',
  'black leather jacket for men',
  'something red for a summer party',
  'comfortable running shoes for women',
  'महिलाओं के लिए गहने',
]

interface SearchExamplesProps {
  onSelect: (query: string) => void
  disabled?: boolean
}

export function SearchExamples({ onSelect, disabled = false }: SearchExamplesProps) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
      <span className="text-sm text-muted mr-1">Try:</span>
      {EXAMPLE_QUERIES.map((query) => (
        <button
          key={query}
          type="button"
          onClick={() => onSelect(query)}
          disabled={disabled}
          className="text-sm px-3 py-1.5 bg-white border border-border rounded-full text-secondary hover:text-primary hover:border-stone-400 disabled:opacity-50 transition-colors"
        >
          {query}
        </button>
      ))}
    </div>
  )
}
