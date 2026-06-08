import { useMemo } from "react";
import { buildHistoryThreads, filterHistoryThreads } from "../../history/historyThreads";
import { useChatStore } from "../../store/chatStore";
import { useHistory } from "../../hooks/useHistory";
import type { HistoryThread, WhoAmIResponse } from "../../types";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  onSelectThread: (thread: HistoryThread) => void;
  whoAmI?: WhoAmIResponse | null;
  loggedIn?: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
}

export function Sidebar({
  onSelectThread,
  whoAmI,
  loggedIn,
  onLogin,
  onLogout,
}: SidebarProps) {
  const history = useChatStore((s) => s.history);
  const setHistory = useChatStore((s) => s.setHistory);
  const historySearch = useChatStore((s) => s.historySearch);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
  const sessionId = useChatStore((s) => s.sessionId);
  const mode = useChatStore((s) => s.mode);
  const setMode = useChatStore((s) => s.setMode);
  const startNewChat = useChatStore((s) => s.startNewChat);
  const { clear } = useHistory();

  const filteredThreads = useMemo(() => {
    return filterHistoryThreads(buildHistoryThreads(history), historySearch).slice(0, 20);
  }, [history, historySearch]);

  const userLabel = whoAmI?.user_id ?? (loggedIn ? "Signed in" : "Guest");
  const planLabel = whoAmI?.plan_tier ?? (loggedIn ? "Session active" : "Local session");

  const handleClearAll = async () => {
    if (!window.confirm("Clear chat history?")) return;
    await clear(sessionId ?? undefined);
    setHistory([]);
  };

  return (
    <aside className={styles.sidebar} aria-label="Primary navigation">
      <div className={styles.brand}>
        <h1>CortexAI</h1>
        <p>LLM Gateway</p>
      </div>

      <button id="historyNewChatBtn" type="button" className={styles.newChatButton} onClick={startNewChat}>
        <span aria-hidden="true">+</span>
        New Chat
      </button>

      <nav className={styles.nav} aria-label="Workspace">
        <button
          type="button"
          className={mode === "single" ? styles.navItemActive : styles.navItem}
          onClick={() => setMode("single")}
        >
          <Icon name="ask" />
          <span>Ask</span>
        </button>
        <button
          type="button"
          className={mode === "compare" ? styles.navItemActive : styles.navItem}
          onClick={() => setMode("compare")}
        >
          <Icon name="compare" />
          <span>Compare</span>
        </button>
      </nav>

      <div className={styles.historyBlock}>
        <div className={styles.historyHeader}>
          <span>History</span>
          {history.length > 0 && (
            <button type="button" onClick={handleClearAll}>
              Clear
            </button>
          )}
        </div>
        <input
          id="historySearch"
          className={styles.historySearch}
          value={historySearch}
          onChange={(event) => setHistorySearch(event.target.value)}
          placeholder="Search history"
          aria-label="Search history"
        />
        <ul className={styles.historyList}>
          {filteredThreads.map((thread) => (
            <li key={thread.key}>
              <button
                type="button"
                className={thread.sessionId === sessionId ? styles.historyItemActive : undefined}
                onClick={() => onSelectThread(thread)}
                title={thread.title}
              >
                <span>{thread.title}</span>
                <small>
                  {formatMode(thread.mode)} / {thread.turnCount} {thread.turnCount === 1 ? "turn" : "turns"}
                </small>
                <small>
                  {thread.providerLabel}:{thread.modelLabel}
                </small>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        className={styles.profile}
        onClick={loggedIn ? onLogout : onLogin}
        disabled={!loggedIn && !onLogin}
      >
        <span className={styles.avatar} aria-hidden="true">
          {(userLabel[0] ?? "G").toUpperCase()}
        </span>
        <span className={styles.profileText}>
          <strong>{userLabel}</strong>
          <span>{planLabel}</span>
        </span>
      </button>
    </aside>
  );
}

function formatMode(mode: HistoryThread["mode"]): string {
  if (mode === "single") return "Ask";
  if (mode === "compare") return "Compare";
  return "Mixed";
}

function Icon({ name }: { name: "ask" | "compare" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
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
    </svg>
  );
}
