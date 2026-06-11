import styles from "./ResponseLoadingState.module.css";

export type ResponseLoadingMode = "ask" | "compare";

interface ResponseLoadingStateProps {
  mode: ResponseLoadingMode;
  researchEnabled?: boolean;
  optimizeEnabled?: boolean;
}

export function ResponseLoadingState({
  mode,
  researchEnabled = false,
  optimizeEnabled = false,
}: ResponseLoadingStateProps) {
  const message = getResponseLoadingMessage({
    mode,
    researchEnabled,
    optimizeEnabled,
  });

  return (
    <div className={styles.loading} role="status" aria-live="polite">
      <div className={styles.statusLine}>
        <span className={styles.sparkle} aria-hidden="true">
          <SparkleIcon />
        </span>
        <span className={styles.message}>{message}</span>
      </div>
      <div className={styles.skeleton} aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function getResponseLoadingMessage({
  mode,
  researchEnabled,
  optimizeEnabled,
}: ResponseLoadingStateProps): string {
  if (optimizeEnabled) return "Refining prompt and preparing response\u2026";
  if (researchEnabled) return "Checking sources and preparing an answer\u2026";
  if (mode === "ask") return "Thinking through your request\u2026";
  return "Generating response\u2026";
}

function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.8 13.8 8l5.2 1.8-5.2 1.8L12 17l-1.8-5.4L5 9.8 10.2 8 12 2.8Z" />
      <path d="m18.5 15 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
    </svg>
  );
}
