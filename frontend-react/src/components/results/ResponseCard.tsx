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
  const badge = getModelBadge(response.provider, response.model);
  const totalTokens = response.token_usage.total_tokens;

  return (
    <article className={`${styles.card} ${hasError ? styles.errorCard : ""}`}>
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h2>{response.model || response.provider}</h2>
          <span className={`${styles.badge} ${styles[badge.tone]}`}>{badge.label}</span>
        </div>
        <div className={styles.metaRow}>
          <span>
            <Icon name="bolt" />
            {response.latency_ms || 0}ms
          </span>
          <span>
            <Icon name="document" />
            {formatTokens(totalTokens)} tokens
          </span>
        </div>
      </header>

      <div className={`${styles.body} ${isStreaming ? styles.streaming : ""}`}>
        {hasError ? (
          <div className={styles.errorMsg}>
            <span aria-hidden="true">!</span>
            {response.error!.message}
          </div>
        ) : (
          <ReactMarkdown>{text || "Waiting for response..."}</ReactMarkdown>
        )}
        {isStreaming && <span className={styles.cursor} aria-hidden="true" />}
      </div>

      {!isStreaming && response.web_source_items.length > 0 && (
        <footer className={styles.sources}>
          <span>Sources</span>
          <ul>
            {response.web_source_items.map((source, index) => (
              <li key={index}>
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.title}
                </a>
              </li>
            ))}
          </ul>
        </footer>
      )}
    </article>
  );
}

function getModelBadge(provider: string, model: string) {
  const value = `${provider} ${model}`.toLowerCase();
  if (value.includes("gemini")) return { label: "FASTEST", tone: "fastest" as const };
  if (value.includes("grok") || value.includes("xai")) return { label: "RAW", tone: "raw" as const };
  if (value.includes("claude") || value.includes("anthropic")) {
    return { label: "ADVANCED", tone: "advanced" as const };
  }
  if (value.includes("deepseek")) return { label: "DEEP", tone: "deep" as const };
  return { label: "LEGACY", tone: "legacy" as const };
}

function formatTokens(tokens: number) {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(tokens >= 10000 ? 0 : 1)}k`;
  return tokens.toLocaleString();
}

function Icon({ name }: { name: "bolt" | "document" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "bolt" ? (
        <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />
      ) : (
        <>
          <path d="M7 3h7l4 4v14H7z" />
          <path d="M14 3v5h4" />
          <path d="M9 13h6" />
          <path d="M9 17h6" />
        </>
      )}
    </svg>
  );
}
