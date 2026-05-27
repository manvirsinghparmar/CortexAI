import { useChatStore } from "../../store/chatStore";
import { ResponseCard } from "./ResponseCard";
import styles from "./ResultsSection.module.css";

export function ResultsSection() {
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);
  const streamingText = useChatStore((s) => s.streamingText);
  const mode = useChatStore((s) => s.mode);

  const hasContent = responses.length > 0 || streaming;
  if (!hasContent) return null;

  const visibleResponses =
    streaming && mode === "single"
      ? [
          {
            request_id: "streaming",
            text: streamingText,
            provider: "assistant",
            model: "Working",
            latency_ms: 0,
            token_usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
            estimated_cost: 0,
            cost_currency: "USD",
            web_source_items: [],
            timestamp: new Date().toISOString(),
          },
        ]
      : responses;

  return (
    <section
      className={mode === "compare" ? styles.compareSection : styles.singleSection}
      aria-live="polite"
      aria-label="AI responses"
    >
      <div className={mode === "compare" ? styles.compareGrid : styles.singleGrid}>
        {visibleResponses.map((response) => (
          <ResponseCard
            key={response.request_id}
            response={response}
            isStreaming={streaming && mode === "single"}
            streamingText={streamingText}
          />
        ))}
      </div>
    </section>
  );
}
