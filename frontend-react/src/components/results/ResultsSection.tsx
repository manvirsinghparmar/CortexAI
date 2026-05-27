import { useChatStore } from "../../store/chatStore";
import { ResponseCard } from "./ResponseCard";

export function ResultsSection() {
  const responses = useChatStore((s) => s.responses);
  const streaming = useChatStore((s) => s.streaming);
  const streamingText = useChatStore((s) => s.streamingText);
  const clearResponses = useChatStore((s) => s.clearResponses);
  const mode = useChatStore((s) => s.mode);

  const hasContent = responses.length > 0 || streaming;
  if (!hasContent) return null;

  const isCompare = mode === "compare";
  const colClass = isCompare
    ? responses.length === 2
      ? "grid-cols-1 md:grid-cols-2"
      : "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
    : "grid-cols-1 max-w-3xl mx-auto w-full";

  return (
    <section className="mb-4 w-full" aria-live="polite" aria-label="AI responses">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">
          {isCompare ? `${responses.length || "…"} responses` : "Response"}
        </h2>
        <button
          onClick={clearResponses}
          className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
        >
          Clear
        </button>
      </div>

      <div className={`grid gap-4 ${colClass}`}>
        {streaming && mode === "single" && (
          <ResponseCard
            response={{
              request_id: "streaming",
              text: streamingText,
              provider: "assistant",
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

        {!streaming &&
          responses.map((r) => (
            <ResponseCard key={r.request_id} response={r} />
          ))}
      </div>
    </section>
  );
}
