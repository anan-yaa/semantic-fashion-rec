/**
 * Outfit builder page: describe an occasion, get a top, bottom, footwear and accessory
 */

'use client'

import { useEffect, useState } from 'react'
import { OutfitResponse } from '@/types/product'
import { buildOutfit, RateLimitError } from '@/lib/api'
import { SiteHeader } from '@/components/SiteHeader'
import { SearchBar } from '@/components/SearchBar'
import { SearchExamples } from '@/components/SearchExamples'
import { QueryUnderstanding } from '@/components/QueryUnderstanding'
import { OutfitView } from '@/components/OutfitView'
import { ErrorState } from '@/components/ErrorState'

const EXAMPLES = [
  'I need an outfit to go to the beach this summer',
  'outfit for a job interview',
  'warm outfit for a winter evening',
  'casual outfit for a college day',
]

const WEARERS = ['Men', 'Women', 'Boys', 'Girls']

export default function OutfitPage() {
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [gender, setGender] = useState('')
  const [run, setRun] = useState(0)
  const [result, setResult] = useState<OutfitResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isRateLimited, setIsRateLimited] = useState(false)

  useEffect(() => {
    if (!activeQuery) return
    let cancelled = false
    setIsLoading(true)
    setError(null)
    buildOutfit(activeQuery, { filters: gender ? { gender } : undefined })
      .then((data) => {
        if (!cancelled) setResult(data)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Could not build an outfit.')
        setIsRateLimited(err instanceof RateLimitError)
        setResult(null)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [activeQuery, gender, run])

  const submit = (q: string) => {
    setQuery(q)
    setActiveQuery(q)
    setRun((n) => n + 1)
  }

  const clear = () => {
    setQuery('')
    setActiveQuery('')
    setResult(null)
    setError(null)
  }

  return (
    <main className="min-h-screen bg-surface text-primary">
      <SiteHeader active="outfit" />

      <section className="border-b border-border bg-white">
        <div className={`max-w-3xl mx-auto px-4 text-center ${activeQuery ? 'py-6' : 'py-14'}`}>
          {!activeQuery && (
            <>
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">Build an outfit</h1>
              <p className="mt-3 mb-8 text-secondary">
                Say what it&apos;s for. You get a top, bottom, footwear and accessory that fit the occasion, with
                alternatives for each.
              </p>
            </>
          )}
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={submit}
            onClear={clear}
            isLoading={isLoading}
            placeholder="What do you need an outfit for?"
            submitLabel="Build outfit"
            loadingLabel="Building"
          />
          <div className="mt-3 flex items-center justify-center gap-2 text-sm text-secondary">
            <label htmlFor="outfit-gender">For</label>
            <select
              id="outfit-gender"
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              disabled={isLoading}
              className="rounded-full border border-border bg-white px-3 py-1 text-primary"
            >
              <option value="">Anyone (we&apos;ll decide)</option>
              {WEARERS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
          {!activeQuery && <SearchExamples onSelect={submit} disabled={isLoading} examples={EXAMPLES} />}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 py-8">
        {error ? (
          <ErrorState
            message={error}
            onRetry={() => setRun((n) => n + 1)}
            {...(isRateLimited ? { title: "You're searching too quickly", hint: null } : {})}
          />
        ) : isLoading ? (
          <p className="text-secondary">Putting an outfit together…</p>
        ) : result ? (
          <>
            <div className="mb-8 space-y-3">
              <h2 className="text-xl font-medium">
                Outfit for “{result.query}”{result.gender ? ` · ${result.gender}` : ''}
              </h2>
              <QueryUnderstanding understanding={result.understanding} />
            </div>
            <OutfitView slots={result.slots} />
          </>
        ) : null}
      </section>
    </main>
  )
}
