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

function SparkIcon() {
  return (
    <svg className="h-4 w-4 text-accent" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 2l1.8 5.6L19.5 9.5l-5.7 1.9L12 17l-1.8-5.6L4.5 9.5l5.7-1.9L12 2z" />
      <path d="M19 15l.8 2.2 2.2.8-2.2.8L19 21l-.8-2.2-2.2-.8 2.2-.8L19 15z" />
    </svg>
  )
}

interface QueryUnderstandingProps {
  understanding: Understanding | null | undefined
}

export function QueryUnderstanding({ understanding }: QueryUnderstandingProps) {
  if (!understanding) return null

  if (!understanding.used_llm) {
    const message = understanding.fallback_reason && FALLBACK_MESSAGES[understanding.fallback_reason]
    return message ? (
      <p className="flex items-center gap-2 text-sm text-secondary">
        <svg className="h-4 w-4 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5M12 8h.01" strokeLinecap="round" />
        </svg>
        {message}
      </p>
    ) : null
  }

  const filters = Object.entries(understanding.inferred_filters)
  const translation = understanding.translated ? understanding.english_query : null
  if (!translation && filters.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" aria-label="Query understanding">
      <SparkIcon />
      <span className="text-secondary">{translation ? 'Searched in English as:' : 'Understood as:'}</span>
      {translation && (
        <span className="px-2.5 py-0.5 rounded-full border border-accent-border bg-white text-primary">
          “{translation}”
        </span>
      )}
      {filters.map(([field, value]) => (
        <span key={field} className="px-2.5 py-0.5 rounded-full bg-accent-soft text-accent">
          {FILTER_LABELS[field] ?? field}: {value}
        </span>
      ))}
    </div>
  )
}
