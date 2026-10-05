/**
 * Product types for API responses and component props
 */

export interface Product {
  id: string
  external_product_id: string
  name: string
  category: string | null
  subcategory: string | null
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

export interface SearchFilters {
  category?: string
  gender?: string
  color?: string
  season?: string
  availability?: boolean
}

export interface QueryUnderstanding {
  used_llm: boolean
  keywords: string | null
  inferred_filters: Partial<Record<'category' | 'gender' | 'color' | 'season', string>>
  fallback_reason: 'unsupported_query' | 'llm_unavailable' | null
}

export interface SearchResponse {
  products: Product[]
  query: string
  method: SearchMethod
  total_products: number
  took_ms: number
  /** Null when query understanding is disabled on the backend */
  understanding: QueryUnderstanding | null
}
