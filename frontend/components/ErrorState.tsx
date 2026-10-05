/**
 * ErrorState: Display when API fails or backend unavailable
 */

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
  title?: string
  /** Extra line under the message; pass null to hide it */
  hint?: string | null
}

export function ErrorState({
  message = 'Failed to load products. Please check that the backend is running.',
  onRetry,
  title = 'Something went wrong',
  hint = 'Is the backend running on port 8000?',
}: ErrorStateProps) {
  return (
    <div className="mx-auto max-w-lg border border-red-200 bg-red-50 rounded-xl p-6 text-center">
      <p className="font-medium text-red-900">{title}</p>
      <p className="mt-1 text-sm text-red-800">{message}</p>
      {hint && <p className="mt-1 text-xs text-red-700/80">{hint}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-5 py-2 text-sm bg-red-600 text-white rounded-full hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
