import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getProducts, getHealth, searchProducts } from '@/lib/api'

// Mock fetch
global.fetch = vi.fn()

describe('API client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getProducts', () => {
    it('makes correct API call with default parameters', async () => {
      const mockResponse = {
        items: [],
        total: 0,
        page: 1,
        page_size: 24,
        total_pages: 0,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await getProducts()

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/products?page=1&page_size=24'),
        expect.objectContaining({
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        })
      )
      expect(result).toEqual(mockResponse)
    })

    it('makes correct API call with custom parameters', async () => {
      const mockResponse = {
        items: [],
        total: 0,
        page: 2,
        page_size: 50,
        total_pages: 0,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      await getProducts(2, 50)

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('page=2&page_size=50'),
        expect.any(Object)
      )
    })

    it('throws error on HTTP failure', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })

      await expect(getProducts()).rejects.toThrow()
    })

    it('throws error on network failure', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

      await expect(getProducts()).rejects.toThrow('Network error')
    })
  })

  describe('searchProducts', () => {
    it('makes correct API call with default method and limit', async () => {
      const mockResponse = {
        products: [],
        query: 'blue shirt',
        method: 'hybrid',
        total_products: 0,
        took_ms: 12.5,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await searchProducts('blue shirt')

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/search'),
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: 'blue shirt',
            method: 'hybrid',
            filters: undefined,
            limit: 50,
          }),
        })
      )
      expect(result).toEqual(mockResponse)
    })

    it('passes through method, filters, and limit overrides', async () => {
      const mockResponse = {
        products: [],
        query: 'red dress',
        method: 'vector',
        total_products: 0,
        took_ms: 5,
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      await searchProducts('red dress', {
        method: 'vector',
        filters: { gender: 'Women' },
        limit: 10,
      })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/search'),
        expect.objectContaining({
          body: JSON.stringify({
            query: 'red dress',
            method: 'vector',
            filters: { gender: 'Women' },
            limit: 10,
          }),
        })
      )
    })

    it('throws error on HTTP failure', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })

      await expect(searchProducts('shirt')).rejects.toThrow()
    })

    it('throws error on network failure', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

      await expect(searchProducts('shirt')).rejects.toThrow('Network error')
    })
  })

  describe('getHealth', () => {
    it('makes correct health check call', async () => {
      const mockResponse = { status: 'healthy', database: 'connected' }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await getHealth()

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({
          method: 'GET',
        })
      )
      expect(result).toEqual(mockResponse)
    })
  })
})
