/**
 * Pagination: Navigation controls for product pages
 */

interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  isLoading?: boolean
}

const BUTTON =
  'px-4 py-2 text-sm bg-white border border-border rounded-full hover:border-stone-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors'

export function Pagination({
  page,
  totalPages,
  onPageChange,
  isLoading = false,
}: PaginationProps) {
  if (totalPages <= 1) {
    return null
  }

  return (
    <nav className="flex items-center justify-center gap-4 mt-10" aria-label="Pagination">
      <button onClick={() => onPageChange(page - 1)} disabled={page === 1 || isLoading} className={BUTTON}>
        ← Previous
      </button>

      <div className="text-sm text-secondary">
        Page <strong className="text-primary">{page.toLocaleString()}</strong> of{' '}
        <strong className="text-primary">{totalPages.toLocaleString()}</strong>
      </div>

      <button onClick={() => onPageChange(page + 1)} disabled={page === totalPages || isLoading} className={BUTTON}>
        Next →
      </button>
    </nav>
  )
}
