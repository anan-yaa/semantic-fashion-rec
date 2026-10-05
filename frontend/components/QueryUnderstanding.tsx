/**
 * QueryUnderstanding: shows what the LLM extracted from the search query
 */

import { QueryUnderstanding as Understanding } from '@/types/product'

const FILTER_LABELS: Record<string, string> = {
  category: 'Category',
  gender: 'Gender',
  color: 'Color',
  season: 'Season',
}

const FALLBACK_MESSAGES: Record<NonNullable<Understanding['fallback_reason']>, string> = {
  unsupported_query: 'Non-English query: matched by multilingual semantic search (LLM skipped).',
  llm_unavailable: 'LLM unavailable: showing semantic and keyword results for your exact words.',
}

interface QueryUnderstandingProps {
  understanding: Understanding | null | undefined
}

export function QueryUnderstanding({ understanding }: QueryUnderstandingProps) {
  if (!understanding) return null

  if (!understanding.used_llm) {
    const message = understanding.fallback_reason && FALLBACK_MESSAGES[understanding.fallback_reason]
    return message ? <p className="mb-4 text-sm text-secondary">{message}</p> : null
  }

  const filters = Object.entries(understanding.inferred_filters)

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 text-sm" aria-label="Query understanding">
      <span className="text-secondary">Understood as:</span>
      {understanding.keywords && (
        <span className="px-2 py-0.5 border border-border rounded-full">“{understanding.keywords}”</span>
      )}
      {filters.map(([field, value]) => (
        <span key={field} className="px-2 py-0.5 border border-border rounded-full bg-hover">
          {FILTER_LABELS[field] ?? field}: {value}
        </span>
      ))}
    </div>
  )
}
