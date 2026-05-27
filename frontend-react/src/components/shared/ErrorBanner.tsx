interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  onDismiss: () => void;
}

export function ErrorBanner({ message, onRetry, onDismiss }: ErrorBannerProps) {
  return (
    <div className="flex items-start gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl px-4 py-3 mb-4" role="alert" aria-live="assertive" aria-atomic="true">
      <span className="text-red-500 shrink-0 mt-0.5" aria-hidden="true">⚠</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-700 dark:text-red-400">Something went wrong</p>
        <p className="text-xs text-red-600 dark:text-red-500 mt-0.5">{message}</p>
        {onRetry && (
          <button
            className="text-xs text-red-700 dark:text-red-400 underline mt-1 hover:no-underline"
            type="button"
            onClick={onRetry}
          >
            Retry
          </button>
        )}
      </div>
      <button
        className="text-red-400 hover:text-red-600 dark:hover:text-red-300 text-lg leading-none shrink-0"
        type="button"
        aria-label="Dismiss error"
        onClick={onDismiss}
      >
        ×
      </button>
    </div>
  );
}
