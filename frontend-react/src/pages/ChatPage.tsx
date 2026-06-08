import { useEffect, useMemo, useState } from "react";
import { fetchHistory } from "../api/history";
import { PromptComposer } from "../components/composer/PromptComposer";
import { ResultsSection } from "../components/results/ResultsSection";
import { ErrorBanner } from "../components/shared/ErrorBanner";
import { ExampleChips } from "../components/shared/ExampleChips";
import { Sidebar } from "../components/layout/Sidebar";
import { buildHistoryThreads, filterHistoryThreads } from "../history/historyThreads";
import { useAuth } from "../hooks/useAuth";
import { useChat } from "../hooks/useChat";
import { useHistory } from "../hooks/useHistory";
import { useModels } from "../hooks/useModels";
import { useChatStore } from "../store/chatStore";
import type { ChatMode, HistoryThread } from "../types";
import styles from "./ChatPage.module.css";

type MobilePanel = "chat" | "history";

export function ChatPage() {
  const { whoAmI, cognitoConfig, loading: authLoading, loggedIn, login, logout } = useAuth();
  const { models, error: modelsError } = useModels(!authLoading);
  const backendOffline = !!modelsError && !authLoading;
  const { load: loadHistory } = useHistory();
  const { submit } = useChat();
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("chat");
  const error = useChatStore((s) => s.error);
  const setError = useChatStore((s) => s.setError);
  const hydrateFromHistoryThread = useChatStore((s) => s.hydrateFromHistoryThread);
  const mode = useChatStore((s) => s.mode);
  const setMode = useChatStore((s) => s.setMode);
  const startNewChat = useChatStore((s) => s.startNewChat);
  const authEnabled = cognitoConfig?.enabled ?? false;

  useEffect(() => {
    if (!authLoading) void loadHistory();
  }, [authLoading, loadHistory]);

  const handleSelectHistoryThread = async (thread: HistoryThread) => {
    try {
      const entries = thread.sessionId
        ? await fetchHistory(500, thread.sessionId)
        : thread.entries;
      const completeThread = buildHistoryThreads(entries)[0] ?? thread;
      hydrateFromHistoryThread(completeThread);
      setMobilePanel("chat");
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : "Failed to load chat history");
    }
  };

  const handleMobileMode = (nextMode: ChatMode) => {
    setMode(nextMode);
    setMobilePanel("chat");
  };

  return (
    <div className={styles.layout}>
      <Sidebar
        onSelectThread={(thread) => void handleSelectHistoryThread(thread)}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? login : undefined}
        onLogout={authEnabled ? logout : undefined}
      />

      <main className={styles.main}>
        <header className={styles.mobileTopbar}>
          <button
            type="button"
            className={styles.mobileBrand}
            onClick={() => {
              startNewChat();
              setMobilePanel("chat");
            }}
          >
            CortexAI
          </button>
          <button
            type="button"
            className={styles.iconButton}
            aria-label={loggedIn ? "Account" : "Guest account"}
            onClick={loggedIn ? logout : login}
          >
            <Icon name="account" />
          </button>
        </header>

        <header className={styles.topbar}>
          <nav className={styles.tabs} aria-label="Chat mode">
            <button
              id="btnSingleMode"
              type="button"
              className={`${styles.tab} ${mode === "single" ? styles.activeTab : ""}`}
              onClick={() => setMode("single")}
            >
              Ask
            </button>
            <button
              id="btnCompareMode"
              type="button"
              className={`${styles.tab} ${mode === "compare" ? styles.activeTab : ""}`}
              onClick={() => setMode("compare")}
            >
              Compare
            </button>
          </nav>
          <div className={styles.topActions} aria-label="Workspace actions">
            <button type="button" className={styles.iconButton} aria-label="New chat" onClick={startNewChat}>
              <Icon name="plus" />
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
          {backendOffline && <BackendBanner />}
          {mobilePanel === "history" ? (
            <MobileHistory onSelectThread={(thread) => void handleSelectHistoryThread(thread)} />
          ) : (
            <>
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
            </>
          )}
        </div>

        {mobilePanel === "chat" && (
          <div className={styles.composerWrap}>
            <PromptComposer models={models} />
          </div>
        )}

        <nav className={styles.mobileNav} aria-label="Mobile navigation">
          <button
            type="button"
            className={mobilePanel === "chat" && mode === "single" ? styles.mobileNavActive : ""}
            onClick={() => handleMobileMode("single")}
          >
            <Icon name="ask" />
            <span>Ask</span>
          </button>
          <button
            type="button"
            className={mobilePanel === "chat" && mode === "compare" ? styles.mobileNavActive : ""}
            onClick={() => handleMobileMode("compare")}
          >
            <Icon name="compare" />
            <span>Compare</span>
          </button>
          <button
            type="button"
            className={mobilePanel === "history" ? styles.mobileNavActive : ""}
            onClick={() => setMobilePanel("history")}
          >
            <Icon name="history" />
            <span>History</span>
          </button>
        </nav>
      </main>
    </div>
  );
}

function BackendBanner() {
  return (
    <div className={styles.backendBanner}>
      Backend not connected. Chat, compare, model catalog, history, and attachments require the
      FastAPI backend at port 8000.
    </div>
  );
}

function MobileHistory({ onSelectThread }: { onSelectThread: (thread: HistoryThread) => void }) {
  const history = useChatStore((s) => s.history);
  const historySearch = useChatStore((s) => s.historySearch);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
  const startNewChat = useChatStore((s) => s.startNewChat);
  const filteredThreads = useMemo(() => {
    return filterHistoryThreads(buildHistoryThreads(history), historySearch);
  }, [history, historySearch]);

  return (
    <section className={styles.mobileHistory} aria-label="History">
      <button type="button" className={styles.mobileNewChat} onClick={startNewChat}>
        New Chat
      </button>
      <input
        id="mobileHistorySearch"
        value={historySearch}
        onChange={(event) => setHistorySearch(event.target.value)}
        placeholder="Search history"
        aria-label="Search history"
      />
      <ul>
        {filteredThreads.map((thread) => (
          <li key={thread.key}>
            <button type="button" onClick={() => onSelectThread(thread)}>
              <span>{thread.title}</span>
              <small>
                {formatHistoryMode(thread.mode)} / {thread.turnCount}{" "}
                {thread.turnCount === 1 ? "turn" : "turns"}
              </small>
              <small>
                {thread.providerLabel}:{thread.modelLabel}
              </small>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatHistoryMode(mode: HistoryThread["mode"]): string {
  if (mode === "single") return "Ask";
  if (mode === "compare") return "Compare";
  return "Mixed";
}

function Icon({
  name,
}: {
  name: "account" | "plus" | "ask" | "compare" | "history";
}) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "account" && (
        <>
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 20a7 7 0 0 1 14 0" />
          <circle cx="12" cy="12" r="10" />
        </>
      )}
      {name === "plus" && (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v8" />
          <path d="M8 12h8" />
        </>
      )}
      {name === "ask" && (
        <>
          <path d="M4 5h16v10H8l-4 4z" />
          <path d="M9 9h6" />
          <path d="M9 12h4" />
        </>
      )}
      {name === "compare" && (
        <>
          <path d="M5 5h6v14H5z" />
          <path d="M13 5h6v14h-6z" />
        </>
      )}
      {name === "history" && (
        <>
          <path d="M3 12a9 9 0 1 0 3-6.7" />
          <path d="M3 4v5h5" />
          <path d="M12 7v5l3 2" />
        </>
      )}
    </svg>
  );
}
