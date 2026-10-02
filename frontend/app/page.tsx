/**
 * Main catalogue page
 * Displays products with pagination, search (not yet functional)
 */

'use client'

import { useEffect, useState } from 'react'
import { PaginatedProductResponse, Product } from '@/types/product'
import { getProducts } from '@/lib/api'
import { ProductGrid } from '@/components/ProductGrid'
import { SearchBar } from '@/components/SearchBar'
import { SearchExamples } from '@/components/SearchExamples'
import { Pagination } from '@/components/Pagination'
import { ErrorState } from '@/components/ErrorState'

const PAGE_SIZE = 24

export default function CataloguePage() {
  const [page, setPage] = useState(1)
  const [products, setProducts] = useState<Product[]>([])
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch products on page change
  useEffect(() => {
    const fetchProducts = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data: PaginatedProductResponse = await getProducts(page, PAGE_SIZE)
        setProducts(data.items)
        setTotalPages(data.total_pages)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load products. Is the backend running?'
        )
        setProducts([])
      } finally {
        setIsLoading(false)
      }
    }

    fetchProducts()
  }, [page])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSearch = (_query: string) => {
    // Search functionality will be implemented in Day 2
  }

  const handleExampleSelect = (_query: string) => {
    // Example select will trigger search when semantic search implemented in Day 2
  }

  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-border py-8">
        <div className="max-w-7xl mx-auto px-4">
          <h1 className="text-4xl font-bold text-primary mb-2">Fashion Recommendation System</h1>
          <p className="text-secondary">Semantic fashion search over a 44K-product catalogue</p>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-12">
        {/* Search Section */}
        <section className="mb-12">
          <SearchBar onSearch={handleSearch} isLoading={isLoading} />
          <SearchExamples onSelect={handleExampleSelect} />
        </section>

        {/* Results Section */}
        <section>
          {error ? (
            <ErrorState
              message={error}
              onRetry={() => setPage(page)}
            />
          ) : (
            <>
              <div className="mb-6 text-sm text-secondary">
                Showing {isLoading ? '...' : `${products.length} of ${totalPages * PAGE_SIZE}`} products
              </div>

              <ProductGrid products={products} isLoading={isLoading} />

              <Pagination
                page={page}
                totalPages={totalPages}
                onPageChange={handlePageChange}
                isLoading={isLoading}
              />
            </>
          )}
        </section>
      </div>
    </main>
  )
}
