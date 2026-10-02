/**
 * Centralized API client for all backend communication
 * All HTTP requests must go through this layer
 */

import { PaginatedProductResponse } from '@/types/product'

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
