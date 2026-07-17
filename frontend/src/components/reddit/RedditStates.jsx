export function RedditSkeleton({ rows = 4 }) {
  return <div className="reddit-skeleton" aria-label="Loading Reddit intelligence">{Array.from({ length: rows }, (_, index) => <i key={index} />)}</div>;
}

export function RedditEmptyState({ title, detail, actionLabel, onAction }) {
  return <div className="reddit-empty"><span aria-hidden="true">◌</span><strong>{title}</strong><p>{detail}</p>{actionLabel && onAction && <button type="button" onClick={onAction}>{actionLabel}</button>}</div>;
}

export function RedditErrorState({ message, onRetry }) {
  return <div className="reddit-error" role="alert"><span aria-hidden="true">!</span><div><strong>Reddit intelligence is unavailable</strong><p>{message}</p></div>{onRetry && <button type="button" onClick={onRetry}>Try again</button>}</div>;
}
