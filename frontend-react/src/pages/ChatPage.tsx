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
import styles from "./ChatPage.module.css";

export function ChatPage() {
  const { models } = useModels();
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
    <div className={styles.layout}>
      <Sidebar
        onSelectEntry={handleSelectHistoryEntry}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? login : undefined}
        onLogout={authEnabled ? logout : undefined}
      />

      <main className={styles.main}>
        <header className={styles.topbar}>
          <nav className={styles.tabs} aria-label="Chat mode">
            <button
              type="button"
              className={`${styles.tab} ${mode === "single" ? styles.activeTab : ""}`}
              onClick={() => setMode("single")}
            >
              Ask
            </button>
            <button
              type="button"
              className={`${styles.tab} ${mode === "compare" ? styles.activeTab : ""}`}
              onClick={() => setMode("compare")}
            >
              Compare
            </button>
          </nav>
          <div className={styles.topActions} aria-label="Workspace actions">
            <button type="button" className={styles.iconButton} aria-label="Settings">
              <Icon name="settings" />
            </button>
            <button
              type="button"
              className={styles.iconButton}
              aria-label={loggedIn ? "Account" : "Guest account"}
              onClick={loggedIn ? logout : login}
            >
              <Icon name="account" />
            </button>
          </div>
        </header>

        <div className={styles.canvas}>
          <ResultsSection />
          {error && (
            <ErrorBanner
              message={error}
              onRetry={() => {
                setError(null);
                void submit();
              }}
              onDismiss={() => setError(null)}
            />
          )}
          <ExampleChips />
        </div>

        <div className={styles.composerWrap}>
          <PromptComposer models={models} />
        </div>
      </main>
    </div>
  );
}

function Icon({ name }: { name: "settings" | "account" }) {
  if (name === "settings") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
        <path d="M19.4 15a8 8 0 0 0 .1-1 8 8 0 0 0-.1-1l2-1.5-2-3.5-2.4 1a8.5 8.5 0 0 0-1.7-1L15 5.4h-4l-.4 2.6a8.5 8.5 0 0 0-1.7 1l-2.4-1-2 3.5 2 1.5a8 8 0 0 0-.1 1 8 8 0 0 0 .1 1l-2 1.5 2 3.5 2.4-1a8.5 8.5 0 0 0 1.7 1l.4 2.6h4l.4-2.6a8.5 8.5 0 0 0 1.7-1l2.4 1 2-3.5-2.1-1.5Z" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}
