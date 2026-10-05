/**
 * FilterBar: exact-value filters (from the catalogue's facets) and sort order
 */

import { FacetField, Facets, SearchFilters, SortOrder } from '@/types/product'

const FACET_FIELDS: { field: FacetField; label: string }[] = [
  { field: 'gender', label: 'Gender' },
  { field: 'category', label: 'Category' },
  { field: 'color', label: 'Color' },
  { field: 'season', label: 'Season' },
]

interface FilterBarProps {
  facets: Facets | null
  filters: SearchFilters
  sort: SortOrder
  onFiltersChange: (filters: SearchFilters) => void
  onSortChange: (sort: SortOrder) => void
  /** Browsing has no query, so "relevance" means the catalogue's default order. */
  mode: 'search' | 'browse'
  disabled?: boolean
}

const SELECT =
  'h-9 pl-3 pr-8 text-sm bg-white border border-border rounded-full hover:border-stone-400 focus:outline-none focus:ring-2 focus:ring-primary/70 disabled:opacity-50'

export function FilterBar({
  facets,
  filters,
  sort,
  onFiltersChange,
  onSortChange,
  mode,
  disabled = false,
}: FilterBarProps) {
  const activeCount = FACET_FIELDS.filter(({ field }) => filters[field]).length

  const setFilter = (field: FacetField, value: string) => {
    const next = { ...filters }
    if (value) next[field] = value
    else delete next[field]
    onFiltersChange(next)
  }

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      {FACET_FIELDS.map(({ field, label }) => (
        <select
          key={field}
          aria-label={label}
          value={filters[field] ?? ''}
          onChange={(e) => setFilter(field, e.target.value)}
          disabled={disabled || !facets}
          className={`${SELECT} ${filters[field] ? 'border-primary font-medium' : ''}`}
        >
          <option value="">{label}: All</option>
          {(facets?.[field] ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      ))}

      {activeCount > 0 && (
        <button
          type="button"
          onClick={() => onFiltersChange({})}
          disabled={disabled}
          className="h-9 px-3 text-sm text-secondary hover:text-primary underline-offset-2 hover:underline"
        >
          Clear filters ({activeCount})
        </button>
      )}

      <label className="ml-auto flex items-center gap-2 text-sm text-secondary">
        Sort
        <select
          aria-label="Sort"
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortOrder)}
          disabled={disabled}
          className={SELECT}
        >
          <option value="relevance">{mode === 'search' ? 'Most relevant' : 'Featured'}</option>
          <option value="newest">Newest</option>
          <option value="name">Name A–Z</option>
        </select>
      </label>
    </div>
  )
}
