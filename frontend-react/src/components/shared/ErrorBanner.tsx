import styles from "./ErrorBanner.module.css";

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  onDismiss: () => void;
}

export function ErrorBanner({ message, onRetry, onDismiss }: ErrorBannerProps) {
  return (
    <div className={styles.banner} role="alert" aria-live="assertive" aria-atomic="true">
      <span className={styles.iconWrap} aria-hidden="true">
        <span className={styles.icon}>!</span>
      </span>
      <div className={styles.content}>
        <p className={styles.title}>Something went wrong</p>
        <p className={styles.message}>{message}</p>
        {onRetry && (
          <button className={styles.retryBtn} type="button" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
      <button
        className={styles.closeBtn}
        type="button"
        aria-label="Dismiss error"
        onClick={onDismiss}
      >
        x
      </button>
    </div>
  );
}
