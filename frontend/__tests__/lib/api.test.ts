import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getFacets,
  getFeedbackSummary,
  getHealth,
  getMyVotes,
  getProducts,
  RateLimitError,
  searchProducts,
  sendFeedback,
} from '@/lib/api'

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
            page: 1,
            sort: 'relevance',
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
        page: 3,
        sort: 'newest',
      })

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/search'),
        expect.objectContaining({
          body: JSON.stringify({
            query: 'red dress',
            method: 'vector',
            filters: { gender: 'Women' },
            limit: 10,
            page: 3,
            sort: 'newest',
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

  describe('browse filters and facets', () => {
    it('sends filters and sort as query parameters, skipping empty ones', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) })

      await getProducts(1, 24, { filters: { gender: 'Women', color: '' }, sort: 'name' })

      const url = (global.fetch as any).mock.calls[0][0] as string
      expect(url).toContain('gender=Women')
      expect(url).toContain('sort=name')
      expect(url).not.toContain('color=')
    })

    it('fetches facets', async () => {
      const facets = { category: ['Apparel'], gender: ['Men'], color: ['Red'], season: ['Summer'] }
      ;(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => facets })

      await expect(getFacets()).resolves.toEqual(facets)
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/products/facets'), expect.any(Object))
    })
  })

  describe('rate limiting', () => {
    it('turns a 429 into a RateLimitError with the server message and Retry-After', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        headers: { get: (name: string) => (name === 'Retry-After' ? '7' : null) },
        json: async () => ({ detail: 'Too many searches. Try again in 7 seconds.' }),
      })

      const error = await searchProducts('shirt').catch((e) => e)

      expect(error).toBeInstanceOf(RateLimitError)
      expect(error.message).toBe('Too many searches. Try again in 7 seconds.')
      expect(error.retryAfterSeconds).toBe(7)
    })
  })

  describe('feedback', () => {
    it('sends a vote with its search context', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ vote: -1 }) })

      const stored = await sendFeedback('client-1234', 'red dress', 'p1', -1, {
        position: 5,
        method: 'hybrid',
        sort: 'relevance',
        filters: { gender: 'Women' },
      })

      expect(stored).toBe(-1)
      const [url, init] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/feedback')
      expect(JSON.parse(init.body)).toMatchObject({
        client_id: 'client-1234', query: 'red dress', product_id: 'p1', vote: -1, position: 5,
        method: 'hybrid', filters: { gender: 'Women' },
      })
    })

    it('gets this browser\'s votes for a query', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ votes: { p1: 1 } }) })

      await expect(getMyVotes('client-1234', 'red dress')).resolves.toEqual({ p1: 1 })
      expect((global.fetch as any).mock.calls[0][0]).toContain('/feedback/votes?client_id=client-1234&query=red+dress')
    })

    it('gets the summary', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ total_votes: 3 }) })

      await expect(getFeedbackSummary(5)).resolves.toEqual({ total_votes: 3 })
      expect((global.fetch as any).mock.calls[0][0]).toContain('/feedback/summary?limit=5')
    })
  })
})
