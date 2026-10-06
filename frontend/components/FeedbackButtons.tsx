/**
 * FeedbackButtons: thumbs up / down on a search result. Clicking the active vote removes it.
 */

import { Vote } from '@/types/feedback'

interface FeedbackButtonsProps {
  vote: Vote
  onVote: (vote: Vote) => void
  disabled?: boolean
}

function Thumb({ down = false }: { down?: boolean }) {
  return (
    <svg
      className={`h-4 w-4 ${down ? 'rotate-180' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3z" />
      <path d="M7 10l4-8a2.5 2.5 0 0 1 2.5 2.5V8h5.3a2 2 0 0 1 2 2.3l-1.4 9A2 2 0 0 1 17.4 21H7" />
    </svg>
  )
}

const BUTTON =
  'h-8 w-8 flex items-center justify-center rounded-full border transition-colors disabled:opacity-50 disabled:cursor-not-allowed'

export function FeedbackButtons({ vote, onVote, disabled = false }: FeedbackButtonsProps) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted mr-1">{vote === 0 ? 'Good match?' : 'Thanks!'}</span>
      <button
        type="button"
        aria-label="Good result"
        aria-pressed={vote === 1}
        disabled={disabled}
        onClick={() => onVote(vote === 1 ? 0 : 1)}
        className={`${BUTTON} ${
          vote === 1
            ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
            : 'border-border text-secondary hover:text-emerald-700 hover:border-emerald-300'
        }`}
      >
        <Thumb />
      </button>
      <button
        type="button"
        aria-label="Bad result"
        aria-pressed={vote === -1}
        disabled={disabled}
        onClick={() => onVote(vote === -1 ? 0 : -1)}
        className={`${BUTTON} ${
          vote === -1
            ? 'bg-red-50 border-red-300 text-red-700'
            : 'border-border text-secondary hover:text-red-700 hover:border-red-300'
        }`}
      >
        <Thumb down />
      </button>
    </div>
  )
}
