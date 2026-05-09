import ReactMarkdown from "react-markdown";
import type { ChatResponse } from "../../types";
import styles from "./ResponseCard.module.css";

interface ResponseCardProps {
  response: ChatResponse;
  isStreaming?: boolean;
  streamingText?: string;
}

export function ResponseCard({ response, isStreaming, streamingText }: ResponseCardProps) {
  const text = isStreaming ? (streamingText ?? "") : response.text;
  const hasError = !!response.error;

  return (
    <article className={`${styles.card} ${hasError ? styles.errorCard : ""}`}>
      <div className={styles.cardHeader}>
        <div className={styles.modelInfo}>
          <span className={styles.provider}>{response.provider}</span>
          <span className={styles.model}>{response.model}</span>
        </div>
        <div className={styles.meta}>
          {!isStreaming && (
            <>
              <span className={styles.metaItem}>{response.latency_ms}ms</span>
              <span className={styles.metaItem}>
                {response.token_usage.total_tokens.toLocaleString()} tokens
              </span>
              {response.estimated_cost > 0 && (
                <span className={styles.metaItem}>
                  ${response.estimated_cost.toFixed(4)}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      <div className={`${styles.body} ${isStreaming ? styles.streaming : ""}`}>
        {hasError ? (
          <div className={styles.errorMsg}>
            <span className={styles.errorIcon}>⚠</span>
            {response.error!.message}
          </div>
        ) : (
          <ReactMarkdown>{text}</ReactMarkdown>
        )}
        {isStreaming && <span className={styles.cursor} aria-hidden="true" />}
      </div>

      {!isStreaming && response.web_source_items.length > 0 && (
        <div className={styles.sources}>
          <span className={styles.sourcesLabel}>Sources</span>
          <ul className={styles.sourcesList}>
            {response.web_source_items.map((s, i) => (
              <li key={i} className={styles.sourceItem}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.sourceLink}
                >
                  {s.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
