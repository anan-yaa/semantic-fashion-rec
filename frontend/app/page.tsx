/**
 * Main catalogue page
 * Displays products with pagination, plus hybrid/vector/keyword search via POST /search
 */

'use client'

import { useEffect, useState } from 'react'
import { PaginatedProductResponse, Product, SearchResponse } from '@/types/product'
import { getProducts, searchProducts } from '@/lib/api'
import { ProductGrid } from '@/components/ProductGrid'
import { SearchBar } from '@/components/SearchBar'
import { SearchExamples } from '@/components/SearchExamples'
import { Pagination } from '@/components/Pagination'
import { ErrorState } from '@/components/ErrorState'
import { QueryUnderstanding } from '@/components/QueryUnderstanding'

const PAGE_SIZE = 24

export default function CataloguePage() {
  // Catalogue browsing state
  const [page, setPage] = useState(1)
  const [products, setProducts] = useState<Product[]>([])
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Search state
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const inSearchMode = activeQuery !== ''

  // Fetch catalogue page when browsing (not searching)
  useEffect(() => {
    if (inSearchMode) return

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
  }, [page, inSearchMode])

  // Run search when activeQuery changes
  useEffect(() => {
    if (!inSearchMode) return

    const runSearch = async () => {
      setIsSearching(true)
      setSearchError(null)
      try {
        const data = await searchProducts(activeQuery)
        setSearchResult(data)
      } catch (err) {
        setSearchError(
          err instanceof Error ? err.message : 'Search failed. Is the backend running?'
        )
        setSearchResult(null)
      } finally {
        setIsSearching(false)
      }
    }

    runSearch()
  }, [activeQuery, inSearchMode])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSearchSubmit = (q: string) => {
    setActiveQuery(q)
  }

  const handleClear = () => {
    setQuery('')
    setActiveQuery('')
    setSearchResult(null)
    setSearchError(null)
  }

  const handleExampleSelect = (q: string) => {
    setQuery(q)
    setActiveQuery(q)
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
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={handleSearchSubmit}
            onClear={handleClear}
            isLoading={isSearching}
          />
          <SearchExamples onSelect={handleExampleSelect} />
        </section>

        {/* Results Section */}
        <section>
          {inSearchMode ? (
            searchError ? (
              <ErrorState message={searchError} onRetry={() => setActiveQuery(activeQuery)} />
            ) : (
              <>
                <div className="mb-6 text-sm text-secondary">
                  {isSearching
                    ? 'Searching...'
                    : `Found ${searchResult?.total_products ?? 0} results for "${activeQuery}" ` +
                      `(${searchResult?.method ?? 'hybrid'} search, ${Math.round(searchResult?.took_ms ?? 0)}ms)`}
                </div>
                {!isSearching && <QueryUnderstanding understanding={searchResult?.understanding} />}
                <ProductGrid products={searchResult?.products ?? []} isLoading={isSearching} />
              </>
            )
          ) : error ? (
            <ErrorState message={error} onRetry={() => setPage(page)} />
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
