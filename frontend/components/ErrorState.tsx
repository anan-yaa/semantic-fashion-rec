/**
 * ErrorState: Display when API fails or backend unavailable
 */

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export function ErrorState({
  message = 'Failed to load products. Please check that the backend is running.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="border-2 border-red-200 bg-red-50 rounded-lg p-6 text-center">
      <p className="text-red-900 mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
