import { useEffect, useMemo, useState } from "react";
import { fetchHistory } from "../api/history";
import { PromptComposer } from "../components/composer/PromptComposer";
import { ResultsSection } from "../components/results/ResultsSection";
import { ErrorBanner } from "../components/shared/ErrorBanner";
import { ExampleChips } from "../components/shared/ExampleChips";
import { CortexIcon } from "../components/shared/CortexIcon";
import { AccountMenu } from "../components/layout/AccountMenu";
import { Sidebar } from "../components/layout/Sidebar";
import { formatHistoryDateTime } from "../history/historyDate";
import { buildHistoryThreads, filterHistoryThreads } from "../history/historyThreads";
import { useAuth } from "../hooks/useAuth";
import { useChat } from "../hooks/useChat";
import { useHistory } from "../hooks/useHistory";
import { useModels } from "../hooks/useModels";
import { useChatStore } from "../store/chatStore";
import type { ChatMode, HistoryThread } from "../types";
import brandMarkUrl from "../assets/brand/brand-mark.svg";
import styles from "./ChatPage.module.css";

type MobilePanel = "chat" | "history";

interface MobileHistoryDateGroup {
  key: string;
  label: string;
  threads: HistoryThread[];
}

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
  const setHistory = useChatStore((s) => s.setHistory);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
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

  const handleLogout = () => {
    cancel();
    startNewChat();
    setHistory([]);
    setHistorySearch("");
    setMobilePanel("chat");
    void logout();
  };

  return (
    <div className={styles.layout}>
      <Sidebar
        onSelectThread={(thread) => void handleSelectHistoryThread(thread)}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? login : undefined}
        onLogout={authEnabled ? handleLogout : undefined}
      />

      <main className={styles.main}>
        <header className={styles.mobileTopbar}>
          <span className={styles.mobileBrand}>
            <img src={brandMarkUrl} alt="" aria-hidden="true" />
            <span>CortexAI</span>
          </span>
          <div className={styles.mobileHeaderActions}>
            <button
              type="button"
              className={`${styles.iconButton} ${styles.mobileComposeButton}`}
              aria-label="Start new chat"
              onClick={handleStartNewChat}
            >
              <CortexIcon name="new-chat" />
            </button>
            <AccountMenu
              authEnabled={authEnabled}
              loggedIn={loggedIn}
              onLogin={authEnabled ? login : undefined}
              onLogout={handleLogout}
            />
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
              <CortexIcon name="plus" />
            </button>
            <AccountMenu
              authEnabled={authEnabled}
              loggedIn={loggedIn}
              onLogin={authEnabled ? login : undefined}
              onLogout={handleLogout}
            />
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
            <span className={styles.mobileNavIcon}>
              <CortexIcon name="ask" />
            </span>
            <span>Ask</span>
          </button>
          <button
            type="button"
            className={mobilePanel === "chat" && mode === "compare" ? styles.mobileNavActive : ""}
            onClick={() => handleMobileMode("compare")}
          >
            <span className={styles.mobileNavIcon}>
              <CortexIcon name="compare" />
            </span>
            <span>Compare</span>
          </button>
          <button
            type="button"
            className={mobilePanel === "history" ? styles.mobileNavActive : ""}
            onClick={() => setMobilePanel("history")}
          >
            <span className={styles.mobileNavIcon}>
              <CortexIcon name="history" />
            </span>
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
  const historyGroups = useMemo(() => {
    return groupMobileHistoryThreads(filteredThreads);
  }, [filteredThreads]);

  return (
    <section className={styles.mobileHistory} aria-label="History">
      <div className={styles.mobileHistorySearch}>
        <CortexIcon name="search" />
        <input
          id="mobileHistorySearch"
          value={historySearch}
          onChange={(event) => setHistorySearch(event.target.value)}
          placeholder="Search history"
          aria-label="Search history"
        />
      </div>
      <ul className={styles.mobileHistoryGroups}>
        {historyGroups.map((group) => (
          <li key={group.key} className={styles.mobileHistoryGroup}>
            <span className={styles.mobileHistoryGroupLabel}>{group.label}</span>
            <ul className={styles.mobileHistoryList}>
              {group.threads.map((thread) => (
                <li key={thread.key}>
                  <button
                    type="button"
                    className={thread.sessionId === sessionId ? styles.mobileHistoryActive : ""}
                    onClick={() => onSelectThread(thread)}
                    aria-current={thread.sessionId === sessionId ? "page" : undefined}
                  >
                    <span className={styles.mobileHistoryTop}>
                      <span
                        className={styles.mobileHistoryMode}
                        data-mode={thread.mode}
                      >
                        {formatHistoryMode(thread.mode)}
                      </span>
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

function groupMobileHistoryThreads(threads: HistoryThread[]): MobileHistoryDateGroup[] {
  const groups: MobileHistoryDateGroup[] = [];

  for (const thread of threads) {
    const label = formatMobileHistoryGroupLabel(thread.latestTimestamp);
    const groupKey = label;
    const group = groups.find((candidate) => candidate.key === groupKey);

    if (group) {
      group.threads.push(thread);
    } else {
      groups.push({
        key: groupKey,
        label,
        threads: [thread],
      });
    }
  }

  return groups;
}

function formatMobileHistoryGroupLabel(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Date unavailable";

  const today = new Date();
  if (isSameLocalDate(date, today)) return "Today";

  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (isSameLocalDate(date, yesterday)) return "Yesterday";

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}
