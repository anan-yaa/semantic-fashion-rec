/**
 * Centralized API client for all backend communication
 * All HTTP requests must go through this layer
 */

import {
  Facets,
  PaginatedProductResponse,
  SearchFilters,
  SearchMethod,
  SearchResponse,
  SortOrder,
} from '@/types/product'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ApiErrorResponse {
  message: string
  status: number
}

/**
 * Fetch available products with pagination, optional exact-value filters and sorting
 */
export async function getProducts(
  page: number = 1,
  pageSize: number = 24,
  options?: { filters?: SearchFilters; sort?: SortOrder }
): Promise<PaginatedProductResponse> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    for (const [field, value] of Object.entries(options?.filters ?? {})) {
      if (value !== undefined && value !== '') params.set(field, String(value))
    }
    if (options?.sort) params.set('sort', options.sort)

    const response = await fetch(`${API_URL}/products?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error fetching products:', error)
    throw error
  }
}

/**
 * Search products via hybrid/vector/keyword search
 */
export async function searchProducts(
  query: string,
  options?: {
    method?: SearchMethod
    filters?: SearchFilters
    limit?: number
    page?: number
    sort?: SortOrder
  }
): Promise<SearchResponse> {
  try {
    const response = await fetch(`${API_URL}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        method: options?.method ?? 'hybrid',
        filters: options?.filters,
        limit: options?.limit ?? 50,
        page: options?.page ?? 1,
        sort: options?.sort ?? 'relevance',
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error searching products:', error)
    throw error
  }
}

/**
 * Filter values present in the catalogue (category, gender, color, season)
 */
export async function getFacets(): Promise<Facets> {
  const response = await fetch(`${API_URL}/products/facets`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Health check - verify backend is available
 */
export async function getHealth(): Promise<{ status: string; database: string }> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error('Error checking health:', error)
    throw error
  }
}
