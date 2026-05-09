import { useEffect } from "react";
import { PromptComposer } from "../components/composer/PromptComposer";
import { ResultsSection } from "../components/results/ResultsSection";
import { ErrorBanner } from "../components/shared/ErrorBanner";
import { ExampleChips } from "../components/shared/ExampleChips";
import { Sidebar } from "../components/layout/Sidebar";
import { useModels } from "../hooks/useModels";
import { useHistory } from "../hooks/useHistory";
import { useChat } from "../hooks/useChat";
import { useChatStore } from "../store/chatStore";
import type { HistoryEntry } from "../types";
import styles from "./ChatPage.module.css";

export function ChatPage() {
  const { models, loading: modelsLoading } = useModels();
  const { load: loadHistory } = useHistory();
  const { submit } = useChat();
  const error = useChatStore((s) => s.error);
  const setError = useChatStore((s) => s.setError);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const setResponses = useChatStore((s) => s.setResponses);
  const setStreamingText = useChatStore((s) => s.setStreamingText);
  const setStreaming = useChatStore((s) => s.setStreaming);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleSelectHistoryEntry = (entry: HistoryEntry) => {
    setPrompt(entry.prompt);
    setStreamingText("");
    setStreaming(false);
    // Reconstruct a synthetic response from the history entry
    setResponses([
      {
        request_id: String(entry.id),
        session_id: entry.session_id,
        text: entry.response,
        provider: entry.provider,
        model: entry.model,
        latency_ms: entry.latency_ms ?? 0,
        token_usage: {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: entry.tokens ?? 0,
        },
        estimated_cost: entry.cost ?? 0,
        cost_currency: "USD",
        web_source_items: entry.web_source_items,
        timestamp: entry.timestamp,
      },
    ]);
  };

  return (
    <div className={styles.layout}>
      <Sidebar onSelectEntry={handleSelectHistoryEntry} />

      <main className={styles.main}>
        <ResultsSection />

        {error && (
          <ErrorBanner
            message={error}
            onRetry={() => { setError(null); void submit(); }}
            onDismiss={() => setError(null)}
          />
        )}

        <ExampleChips />

        <div className={styles.composerWrap}>
          {modelsLoading ? (
            <div className={styles.loadingComposer}>Loading models…</div>
          ) : (
            <PromptComposer models={models} />
          )}
        </div>
      </main>
    </div>
  );
}
