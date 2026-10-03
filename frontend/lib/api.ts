/**
 * Centralized API client for all backend communication
 * All HTTP requests must go through this layer
 */

import { PaginatedProductResponse, SearchFilters, SearchMethod, SearchResponse } from '@/types/product'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ApiErrorResponse {
  message: string
  status: number
}

/**
 * Fetch products with pagination
 */
export async function getProducts(
  page: number = 1,
  pageSize: number = 24
): Promise<PaginatedProductResponse> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })

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
  options?: { method?: SearchMethod; filters?: SearchFilters; limit?: number }
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
