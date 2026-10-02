import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getProducts, getHealth } from '@/lib/api'

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
