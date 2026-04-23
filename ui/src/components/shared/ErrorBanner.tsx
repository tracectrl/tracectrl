interface Props {
  error: string
  onRetry?: () => void
  retryLabel?: string
}

export default function ErrorBanner({ error, onRetry, retryLabel = 'Retry' }: Props) {
  return (
    <div className="error-banner" role="alert">
      <span className="error-banner-text">{error}</span>
      {onRetry && (
        <button className="btn btn-ghost btn-sm error-banner-retry" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  )
}
