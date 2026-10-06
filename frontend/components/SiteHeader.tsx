/**
 * SiteHeader: sticky top bar with the brand and navigation
 */

import Link from 'next/link'

interface SiteHeaderProps {
  /** On the search page the brand resets the search instead of navigating */
  onBrandClick?: () => void
  active: 'search' | 'outfit' | 'feedback'
  subtitle?: string
}

const NAV_LINK = 'text-sm px-3 py-1.5 rounded-full transition-colors'

export function SiteHeader({ onBrandClick, active, subtitle }: SiteHeaderProps) {
  const brand = (
    <>
      Thread<span className="text-accent">ly</span>
    </>
  )
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-white/85 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {onBrandClick ? (
            <button onClick={onBrandClick} className="font-semibold tracking-tight text-lg">
              {brand}
            </button>
          ) : (
            <Link href="/" className="font-semibold tracking-tight text-lg">
              {brand}
            </Link>
          )}
          {subtitle && <p className="hidden md:block text-xs text-muted truncate">{subtitle}</p>}
        </div>
        <nav className="flex items-center gap-1" aria-label="Main">
          <Link
            href="/"
            className={`${NAV_LINK} ${active === 'search' ? 'bg-hover text-primary' : 'text-secondary hover:text-primary'}`}
          >
            Search
          </Link>
          <Link
            href="/outfit"
            className={`${NAV_LINK} ${active === 'outfit' ? 'bg-hover text-primary' : 'text-secondary hover:text-primary'}`}
          >
            Outfit builder
          </Link>
          <Link
            href="/feedback"
            className={`${NAV_LINK} ${active === 'feedback' ? 'bg-hover text-primary' : 'text-secondary hover:text-primary'}`}
          >
            Feedback
          </Link>
        </nav>
      </div>
    </header>
  )
}
