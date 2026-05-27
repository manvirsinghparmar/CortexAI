import { useEffect } from "react";
import { PromptComposer } from "../components/composer/PromptComposer";
import { ResultsSection } from "../components/results/ResultsSection";
import { ErrorBanner } from "../components/shared/ErrorBanner";
import { ExampleChips } from "../components/shared/ExampleChips";
import { Sidebar } from "../components/layout/Sidebar";
import { useModels } from "../hooks/useModels";
import { useHistory } from "../hooks/useHistory";
import { useChat } from "../hooks/useChat";
import { useAuth } from "../hooks/useAuth";
import { useChatStore } from "../store/chatStore";
import type { HistoryEntry } from "../types";

export function ChatPage() {
  const { models, loading: modelsLoading } = useModels();
  const { load: loadHistory } = useHistory();
  const { submit } = useChat();
  const { whoAmI, cognitoConfig, loggedIn, login, logout } = useAuth();
  const error = useChatStore((s) => s.error);
  const setError = useChatStore((s) => s.setError);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const setResponses = useChatStore((s) => s.setResponses);
  const setStreamingText = useChatStore((s) => s.setStreamingText);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const mode = useChatStore((s) => s.mode);
  const setMode = useChatStore((s) => s.setMode);

  const authEnabled = cognitoConfig?.enabled ?? false;

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleSelectHistoryEntry = (entry: HistoryEntry) => {
    setPrompt(entry.prompt);
    setStreamingText("");
    setStreaming(false);
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
    <div className="flex h-screen overflow-hidden bg-surface dark:bg-zinc-900">
      <Sidebar
        onSelectEntry={handleSelectHistoryEntry}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? login : undefined}
        onLogout={authEnabled ? logout : undefined}
      />

      <main className="flex flex-col flex-1 overflow-hidden">
        {/* Ask / Compare tab bar */}
        <div className="flex items-center gap-4 px-6 pt-5 pb-0 shrink-0">
          <nav className="flex gap-0.5 bg-zinc-100 dark:bg-zinc-800 rounded-lg p-1">
            <button
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                mode === "single"
                  ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                  : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
              }`}
              onClick={() => setMode("single")}
            >
              Ask
            </button>
            <button
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                mode === "compare"
                  ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm"
                  : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
              }`}
              onClick={() => setMode("compare")}
            >
              Compare
            </button>
          </nav>
        </div>

        {/* Main scrollable content */}
        <div className="flex flex-col flex-1 overflow-y-auto px-6 pt-4 pb-2">
          <ResultsSection />

          {error && (
            <ErrorBanner
              message={error}
              onRetry={() => { setError(null); void submit(); }}
              onDismiss={() => setError(null)}
            />
          )}

          <ExampleChips />
        </div>

        {/* Composer pinned at bottom */}
        <div className="px-6 pb-5 pt-2 shrink-0">
          {modelsLoading ? (
            <div className="text-sm text-zinc-400 text-center py-3">Loading models…</div>
          ) : (
            <PromptComposer models={models} />
          )}
        </div>
      </main>
    </div>
  );
}
