import { useEffect, useMemo, useState } from "react";
import { fetchHistory } from "../api/history";
import { PromptComposer } from "../components/composer/PromptComposer";
import { ResultsSection } from "../components/results/ResultsSection";
import { ErrorBanner } from "../components/shared/ErrorBanner";
import { ExampleChips } from "../components/shared/ExampleChips";
import { Sidebar } from "../components/layout/Sidebar";
import { formatHistoryDateTime } from "../history/historyDate";
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
  const { submit, cancel } = useChat();
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

  const handleStartNewChat = () => {
    cancel();
    startNewChat();
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
          <span className={styles.mobileBrand}>CortexAI</span>
          <div className={styles.mobileHeaderActions}>
            <button
              type="button"
              className={`${styles.iconButton} ${styles.mobileComposeButton}`}
              aria-label="Start new chat"
              onClick={handleStartNewChat}
            >
              <Icon name="compose" />
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
  const sessionId = useChatStore((s) => s.sessionId);
  const filteredThreads = useMemo(() => {
    return filterHistoryThreads(buildHistoryThreads(history), historySearch);
  }, [history, historySearch]);

  return (
    <section className={styles.mobileHistory} aria-label="History">
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
            <button
              type="button"
              className={thread.sessionId === sessionId ? styles.mobileHistoryActive : ""}
              onClick={() => onSelectThread(thread)}
              aria-current={thread.sessionId === sessionId ? "page" : undefined}
            >
              <span className={styles.mobileHistoryTop}>
                <span>{formatHistoryMode(thread.mode)}</span>
                <time dateTime={thread.latestTimestamp}>
                  {formatHistoryDateTime(thread.latestTimestamp) || "Date unavailable"}
                </time>
              </span>
              <span className={styles.mobileHistoryTitle}>{thread.title}</span>
              <small className={styles.mobileHistoryMeta}>
                <span>
                  {thread.turnCount}{" "}
                  {thread.turnCount === 1 ? "turn" : "turns"}
                </span>
                <span aria-hidden="true">·</span>
                <span className={styles.mobileHistoryModel}>{thread.modelLabel}</span>
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
  name: "account" | "plus" | "compose" | "ask" | "compare" | "history";
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
      {name === "compose" && (
        <>
          <path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
          <path d="M18.4 2.6a2.1 2.1 0 0 1 3 3L12.4 14.6a2 2 0 0 1-.9.5l-2.9.9a.5.5 0 0 1-.6-.6l.9-2.9a2 2 0 0 1 .5-.9z" />
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
