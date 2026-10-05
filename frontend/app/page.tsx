/**
 * Main catalogue page
 * Displays products with pagination, plus hybrid/vector/keyword search via POST /search
 */

'use client'

import { useEffect, useState } from 'react'
import {
  Facets,
  PaginatedProductResponse,
  Product,
  SearchFilters,
  SearchResponse,
  SortOrder,
} from '@/types/product'
import { getFacets, getProducts, searchProducts } from '@/lib/api'
import { ProductGrid } from '@/components/ProductGrid'
import { SearchBar } from '@/components/SearchBar'
import { SearchExamples } from '@/components/SearchExamples'
import { Pagination } from '@/components/Pagination'
import { ErrorState } from '@/components/ErrorState'
import { QueryUnderstanding } from '@/components/QueryUnderstanding'
import { FilterBar } from '@/components/FilterBar'

const PAGE_SIZE = 24
const SLOW_SEARCH_MS = 4000

function formatDuration(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

export default function CataloguePage() {
  // Catalogue browsing state
  const [page, setPage] = useState(1)
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [browseRun, setBrowseRun] = useState(0)

  // Filters and sort apply to both browsing and search
  const [facets, setFacets] = useState<Facets | null>(null)
  const [filters, setFilters] = useState<SearchFilters>({})
  const [sort, setSort] = useState<SortOrder>('relevance')

  // Search state
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  // Bumped on every submit/retry so the same query can be searched again.
  const [searchRun, setSearchRun] = useState(0)
  const [searchPage, setSearchPage] = useState(1)
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isSlow, setIsSlow] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const inSearchMode = activeQuery !== ''

  // Load filter values once; filters stay disabled if this fails
  useEffect(() => {
    getFacets()
      .then(setFacets)
      .catch(() => setFacets(null))
  }, [])

  // Fetch catalogue page when browsing (not searching)
  useEffect(() => {
    if (inSearchMode) return
    let cancelled = false

    const fetchProducts = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data: PaginatedProductResponse = await getProducts(page, PAGE_SIZE, { filters, sort })
        if (cancelled) return
        setProducts(data.items)
        setTotal(data.total)
        setTotalPages(data.total_pages)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load products.')
        setProducts([])
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    fetchProducts()
    return () => {
      cancelled = true
    }
  }, [page, inSearchMode, browseRun, filters, sort])

  // Run search when the query is submitted (or retried)
  useEffect(() => {
    if (!inSearchMode) return
    let cancelled = false

    const runSearch = async () => {
      setIsSearching(true)
      setSearchError(null)
      try {
        const data = await searchProducts(activeQuery, {
          filters,
          sort,
          page: searchPage,
          limit: PAGE_SIZE,
        })
        if (!cancelled) setSearchResult(data)
      } catch (err) {
        if (cancelled) return
        setSearchError(err instanceof Error ? err.message : 'Search failed.')
        setSearchResult(null)
      } finally {
        if (!cancelled) setIsSearching(false)
      }
    }

    runSearch()
    return () => {
      cancelled = true
    }
  }, [activeQuery, inSearchMode, searchRun, filters, sort, searchPage])

  // After a few seconds, explain why a search might be slow
  useEffect(() => {
    if (!isSearching) {
      setIsSlow(false)
      return
    }
    const timer = setTimeout(() => setIsSlow(true), SLOW_SEARCH_MS)
    return () => clearTimeout(timer)
  }, [isSearching])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSearchPageChange = (newPage: number) => {
    setSearchPage(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Any change to filters or sort starts again from the first page
  const handleFiltersChange = (next: SearchFilters) => {
    setFilters(next)
    setPage(1)
    setSearchPage(1)
  }

  const handleSortChange = (next: SortOrder) => {
    setSort(next)
    setPage(1)
    setSearchPage(1)
  }

  const runQuery = (q: string) => {
    setQuery(q)
    setActiveQuery(q)
    setSearchPage(1)
    setSearchRun((n) => n + 1)
  }

  const handleClear = () => {
    setQuery('')
    setActiveQuery('')
    setSearchResult(null)
    setSearchError(null)
  }

  const firstShown = (page - 1) * PAGE_SIZE + 1
  const lastShown = Math.min(page * PAGE_SIZE, total)
  const searchTotal = searchResult?.total_products ?? 0
  const searchFirst = (searchPage - 1) * PAGE_SIZE + 1
  const searchLast = Math.min(searchPage * PAGE_SIZE, searchTotal)

  const filterBar = (
    <FilterBar
      facets={facets}
      filters={filters}
      sort={sort}
      onFiltersChange={handleFiltersChange}
      onSortChange={handleSortChange}
      mode={inSearchMode ? 'search' : 'browse'}
      disabled={inSearchMode ? isSearching : isLoading}
    />
  )

  return (
    <main className="min-h-screen bg-surface text-primary">
      {/* Top bar */}
      <header className="sticky top-0 z-10 border-b border-border bg-white/85 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <button onClick={handleClear} className="font-semibold tracking-tight text-lg">
            Fashion<span className="text-accent">Rec</span>
          </button>
          <p className="hidden sm:block text-xs text-muted">
            Semantic + keyword search · local LLM query understanding · {total ? total.toLocaleString() : '44K'} products
          </p>
        </div>
      </header>

      {/* Search hero */}
      <section className="border-b border-border bg-white">
        <div className={`max-w-3xl mx-auto px-4 text-center ${inSearchMode ? 'py-6' : 'py-14'}`}>
          {!inSearchMode && (
            <>
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
                Describe what you&apos;re looking for
              </h1>
              <p className="mt-3 mb-8 text-secondary">
                Search in plain words, in English or Hindi. Meaning, keywords and an LLM work together to find it.
              </p>
            </>
          )}
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={runQuery}
            onClear={handleClear}
            isLoading={isSearching}
          />
          <SearchExamples onSelect={runQuery} disabled={isSearching} />
        </div>
      </section>

      {/* Results */}
      <section className="max-w-6xl mx-auto px-4 py-8">
        {inSearchMode ? (
          searchError ? (
            <ErrorState message={searchError} onRetry={() => setSearchRun((n) => n + 1)} />
          ) : (
            <>
              <div className="mb-6 space-y-3">
                <button onClick={handleClear} className="text-sm text-secondary hover:text-primary transition-colors">
                  ← Back to catalogue
                </button>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-xl font-medium">
                    {isSearching ? 'Searching…' : `${searchTotal} results for “${activeQuery}”`}
                  </h2>
                  {!isSearching && searchResult && (
                    <span className="text-xs text-muted">
                      {searchTotal > 0 && `Showing ${searchFirst}–${searchLast} · `}
                      {searchResult.method} search · {formatDuration(searchResult.took_ms)}
                    </span>
                  )}
                </div>
                {isSearching && isSlow && (
                  <p className="text-sm text-secondary">
                    Still working. The first search after the server starts loads the models and can take a minute.
                  </p>
                )}
                {!isSearching && <QueryUnderstanding understanding={searchResult?.understanding} />}
              </div>
              {filterBar}
              <ProductGrid products={searchResult?.products ?? []} isLoading={isSearching} />
              <Pagination
                page={searchPage}
                totalPages={searchResult?.total_pages ?? 0}
                onPageChange={handleSearchPageChange}
                isLoading={isSearching}
              />
            </>
          )
        ) : error ? (
          <ErrorState message={error} onRetry={() => setBrowseRun((n) => n + 1)} />
        ) : (
          <>
            <div className="mb-6 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl font-medium">Browse the catalogue</h2>
              {!isLoading && total > 0 && (
                <span className="text-sm text-secondary">
                  Showing {firstShown.toLocaleString()}–{lastShown.toLocaleString()} of {total.toLocaleString()} products
                </span>
              )}
            </div>

            {filterBar}
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
    </main>
  )
}
