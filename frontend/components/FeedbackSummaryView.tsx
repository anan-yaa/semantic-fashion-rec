/**
 * FeedbackSummaryView: what users said about search results
 */

import Link from 'next/link'
import { FeedbackSummary } from '@/types/feedback'

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-border rounded-xl p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function searchHref(query: string) {
  return `/?q=${encodeURIComponent(query)}`
}

export function FeedbackSummaryView({ summary }: { summary: FeedbackSummary }) {
  if (summary.total_votes === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-lg">No feedback yet</p>
        <p className="mt-1 text-sm text-secondary">
          Search for something and use the thumbs on each result to say whether it was a good match.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-10">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Votes" value={summary.total_votes.toLocaleString()} />
        <Stat
          label="Good matches"
          value={summary.helpful_rate === null ? '–' : `${Math.round(summary.helpful_rate * 100)}%`}
        />
        <Stat label="Queries rated" value={summary.queries.toLocaleString()} />
        <Stat label="People" value={summary.clients.toLocaleString()} />
      </div>

      <section>
        <h2 className="text-lg font-medium">Queries with the most bad results</h2>
        <p className="text-sm text-secondary mb-3">Where search most needs improving.</p>
        {summary.most_not_helpful.length === 0 ? (
          <p className="text-sm text-secondary">No results have been marked as bad matches.</p>
        ) : (
          <table className="w-full text-sm bg-white border border-border rounded-xl overflow-hidden">
            <thead className="bg-hover text-left text-secondary">
              <tr>
                <th className="px-4 py-2 font-medium">Query</th>
                <th className="px-4 py-2 font-medium text-right">Good</th>
                <th className="px-4 py-2 font-medium text-right">Bad</th>
              </tr>
            </thead>
            <tbody>
              {summary.most_not_helpful.map((q) => (
                <tr key={q.query} className="border-t border-border">
                  <td className="px-4 py-2">
                    <Link href={searchHref(q.query)} className="hover:underline">
                      {q.query}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-right text-emerald-700">{q.helpful}</td>
                  <td className="px-4 py-2 text-right text-red-700">{q.not_helpful}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium mb-3">Recent feedback</h2>
        <ul className="bg-white border border-border rounded-xl divide-y divide-border text-sm">
          {summary.recent.map((r) => (
            <li key={`${r.query}-${r.product_id}-${r.updated_at}`} className="px-4 py-3 flex items-center gap-3">
              <span
                className={`shrink-0 text-xs px-2 py-0.5 rounded-full ${
                  r.vote === 1 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                }`}
              >
                {r.vote === 1 ? 'Good' : 'Bad'}
              </span>
              <span className="min-w-0 truncate">
                {r.product_name} <span className="text-muted">for</span>{' '}
                <Link href={searchHref(r.query)} className="hover:underline">
                  “{r.query}”
                </Link>
              </span>
              <span className="ml-auto shrink-0 text-xs text-muted">
                #{r.position}
                {r.llm_used === false && ' · no LLM'}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
