import { CircleAlert, LoaderCircle, RefreshCw, SearchX } from "lucide-react";

/** Skeleton placeholder grid shown while a search runs. */
export function SkeletonCards({ count = 6 }) {
  return (
    <div className="papers-grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div className="paper-card paper-card--skeleton" key={index}>
          <div className="skeleton skeleton--line skeleton--short" />
          <div className="skeleton skeleton--line skeleton--title" />
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line skeleton--short" />
        </div>
      ))}
    </div>
  );
}

/** Generic empty state with an optional action. */
export function EmptyState({ icon, title, description, action, children }) {
  return (
    <section className="state-block">
      <div className="state-block__icon" aria-hidden="true">
        {icon || <SearchX size={20} />}
      </div>
      <h3 className="state-block__title">{title}</h3>
      {description && <p className="state-block__text">{description}</p>}
      {children}
      {action && (
        <button type="button" className="button button--secondary" onClick={action.onClick}>
          {action.icon || <RefreshCw size={15} />}
          {action.label}
        </button>
      )}
    </section>
  );
}

/** Error state: friendly message, technical code, retry when useful. */
export function ErrorState({ error, onRetry, title = "Something went wrong" }) {
  const message = error?.message || "Unexpected error. Please try again.";
  return (
    <section className="state-block state-block--error" role="alert">
      <div className="state-block__icon" aria-hidden="true">
        <CircleAlert size={20} />
      </div>
      <h3 className="state-block__title">{title}</h3>
      <p className="state-block__text">{message}</p>
      {error?.code && <code className="state-block__code">{error.code}</code>}
      {onRetry && (error?.retryable || !error?.code) && (
        <button type="button" className="button button--secondary" onClick={onRetry}>
          <RefreshCw size={15} aria-hidden="true" />
          Try again
        </button>
      )}
    </section>
  );
}

/** Inline progress line used by long-running operations. */
export function ProgressLine({ label, elapsed, stages = [] }) {
  return (
    <div className="progress-line" role="status" aria-live="polite">
      <LoaderCircle size={16} className="spin" aria-hidden="true" />
      <span className="progress-line__label">{label}</span>
      {stages.length > 0 && (
        <span className="progress-line__stages">
          {stages.map((stage) => (
            <span className="progress-chip" key={stage}>
              {stage}
            </span>
          ))}
        </span>
      )}
      {elapsed > 0 && <span className="progress-line__time">{elapsed}s</span>}
    </div>
  );
}
