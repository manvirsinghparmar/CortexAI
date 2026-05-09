import { useChatStore } from "../../store/chatStore";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

export function ResultsSection() {
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);
  const streamingText = useChatStore((s) => s.streamingText);
  const clearResponses = useChatStore((s) => s.clearResponses);
  const mode = useChatStore((s) => s.mode);

  const hasContent = responses.length > 0 || streaming;
  if (!hasContent) return null;

  return (
    <section
      className={styles.section}
      aria-live="polite"
      aria-label="AI responses"
    >
      <div className={styles.header}>
        <h2 className={styles.title}>Responses</h2>
        <button className={styles.clearBtn} onClick={clearResponses}>
          Clear
        </button>
      </div>

      <div
        className={`${styles.grid} ${mode === "compare" ? styles.compareGrid : ""}`}
        style={mode === "compare" ? { ["--compare-cols" as string]: responses.length || 2 } : undefined}
      >
        {/* Streaming card (single mode) */}
        {streaming && mode === "single" && (
          <ResponseCard
            response={{
              request_id: "streaming",
              text: streamingText,
              provider: "…",
              model: "…",
              latency_ms: 0,
              token_usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
              estimated_cost: 0,
              cost_currency: "USD",
              web_source_items: [],
              timestamp: new Date().toISOString(),
            }}
            isStreaming
            streamingText={streamingText}
          />
        )}

        {/* Final / compare responses */}
        {!streaming &&
          responses.map((r) => (
            <ResponseCard key={r.request_id} response={r} />
          ))}
      </div>
    </section>
  );
}
