/**
 * Feedback page: what users said about search results
 */

'use client'

import { useEffect, useState } from 'react'
import { getFeedbackSummary } from '@/lib/api'
import { FeedbackSummary } from '@/types/feedback'
import { SiteHeader } from '@/components/SiteHeader'
import { FeedbackSummaryView } from '@/components/FeedbackSummaryView'
import { ErrorState } from '@/components/ErrorState'

export default function FeedbackPage() {
  const [summary, setSummary] = useState<FeedbackSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [run, setRun] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError(null)
    getFeedbackSummary(15)
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load feedback.')
      })
    return () => {
      cancelled = true
    }
  }, [run])

  return (
    <main className="min-h-screen bg-surface text-primary">
      <SiteHeader active="feedback" />
      <section className="max-w-4xl mx-auto px-4 py-10">
        <div className="mb-8 flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Search feedback</h1>
            <p className="mt-1 text-sm text-secondary">
              Thumbs up and down given on search results, used to find where search needs to improve.
            </p>
          </div>
          <button
            onClick={() => setRun((n) => n + 1)}
            className="text-sm px-4 py-2 bg-white border border-border rounded-full hover:border-stone-400"
          >
            Refresh
          </button>
        </div>
        {error ? (
          <ErrorState message={error} onRetry={() => setRun((n) => n + 1)} />
        ) : summary ? (
          <FeedbackSummaryView summary={summary} />
        ) : (
          <p className="text-sm text-secondary">Loading…</p>
        )}
      </section>
    </main>
  )
}
