/**
 * Product types for API responses and component props
 */

export interface Product {
  id: string
  external_product_id: string
  name: string
  category: string | null
  subcategory: string | null
  /** Product type, e.g. "Jackets" */
  article_type: string | null
  gender: string | null
  color: string | null
  style: string | null
  season: string | null
  price: number | null
  currency: string
  availability: boolean
}

export interface PaginatedProductResponse {
  items: Product[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type SearchMethod = 'hybrid' | 'vector' | 'keyword'

/** The catalogue has no prices or ratings, so these are the meaningful orders. */
export type SortOrder = 'relevance' | 'newest' | 'name'

export type FacetField = 'category' | 'gender' | 'color' | 'season'

/** Filter values present in the catalogue, per field */
export type Facets = Record<FacetField, string[]>

export interface SearchFilters {
  category?: string
  gender?: string
  color?: string
  season?: string
  availability?: boolean
}

export interface QueryUnderstanding {
  used_llm: boolean
  /** The query wasn't English and was searched in English */
  translated: boolean
  english_query: string | null
  inferred_filters: Partial<Record<'category' | 'gender' | 'color' | 'season', string>>
  fallback_reason: 'unsupported_query' | 'llm_unavailable' | null
}

export interface SearchResponse {
  products: Product[]
  query: string
  method: SearchMethod
  /** Matches across all pages (search ranks at most the top 100) */
  total_products: number
  page: number
  page_size: number
  total_pages: number
  took_ms: number
  /** Null when query understanding is disabled on the backend */
  understanding: QueryUnderstanding | null
}

export interface OutfitSlot {
  key: string
  label: string
  /** The first product is the pick; the rest are alternatives */
  products: Product[]
}

export interface OutfitResponse {
  query: string
  /** Who the outfit was built for, when it could be determined */
  gender: string | null
  slots: OutfitSlot[]
  took_ms: number
  understanding: QueryUnderstanding | null
}
