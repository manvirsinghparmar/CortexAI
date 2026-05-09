import { useChatStore } from "../../store/chatStore";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

const PLACEHOLDER: import("../../types").ChatResponse = {
  request_id: "",
  text: "",
  provider: "…",
  model: "…",
  latency_ms: 0,
  token_usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  estimated_cost: 0,
  cost_currency: "USD",
  web_source_items: [],
  timestamp: "",
};

export function ResultsSection() {
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);
  const streamingText = useChatStore((s) => s.streamingText);
  const compareStreamingTexts = useChatStore((s) => s.compareStreamingTexts);
  const clearResponses = useChatStore((s) => s.clearResponses);
  const clearCompareStreaming = useChatStore((s) => s.clearCompareStreaming);
  const mode = useChatStore((s) => s.mode);

  const compareCardCount = compareStreamingTexts.length;
  const hasContent = responses.length > 0 || streaming || compareCardCount > 0;
  if (!hasContent) return null;

  const colCount =
    mode === "compare"
      ? compareCardCount > 0
        ? compareCardCount
        : responses.length || 2
      : 1;

  const handleClear = () => {
    clearResponses();
    clearCompareStreaming();
  };

  return (
    <section className={styles.section} aria-live="polite" aria-label="AI responses">
      <div className={styles.header}>
        <h2 className={styles.title}>Responses</h2>
        <button className={styles.clearBtn} onClick={handleClear}>
          Clear
        </button>
      </div>

      <div
        className={`${styles.grid} ${mode === "compare" ? styles.compareGrid : ""}`}
        style={mode === "compare" ? { ["--compare-cols" as string]: colCount } : undefined}
      >
        {/* Single mode — streaming */}
        {streaming && mode === "single" && (
          <ResponseCard
            response={{ ...PLACEHOLDER, request_id: "streaming" }}
            isStreaming
            streamingText={streamingText}
          />
        )}

        {/* Compare mode — streaming cards (one per target, appear as each starts) */}
        {mode === "compare" && compareCardCount > 0 &&
          compareStreamingTexts.map((text, i) => (
            <ResponseCard
              key={`compare-stream-${i}`}
              response={{ ...PLACEHOLDER, request_id: `streaming-${i}` }}
              isStreaming={text !== null}
              streamingText={text ?? ""}
            />
          ))}

        {/* Final responses (single or compare after stream completes) */}
        {compareCardCount === 0 &&
          responses.map((r) => <ResponseCard key={r.request_id} response={r} />)}
      </div>
    </section>
  );
}
