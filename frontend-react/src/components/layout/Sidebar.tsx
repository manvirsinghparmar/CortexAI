import { useMemo, useState } from "react";
import { formatHistoryDateTime } from "../../history/historyDate";
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
  const [isCollapsed, setIsCollapsed] = useState(false);
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

  const sidebarClassName = isCollapsed
    ? `${styles.sidebar} ${styles.sidebarCollapsed}`
    : styles.sidebar;
  const collapseLabel = isCollapsed ? "Expand sidebar" : "Collapse sidebar";

  return (
    <aside
      id="desktopSidebar"
      className={sidebarClassName}
      aria-label="Primary navigation"
      data-collapsed={isCollapsed ? "true" : "false"}
    >
      <div className={styles.brand}>
        <div className={styles.brandHeader}>
          <div className={styles.brandText} hidden={isCollapsed}>
            <h1>CortexAI</h1>
            <p>LLM Gateway</p>
          </div>
          <button
            type="button"
            className={styles.collapseButton}
            onClick={() => setIsCollapsed((current) => !current)}
            aria-controls="desktopSidebar"
            aria-expanded={!isCollapsed}
            aria-label={collapseLabel}
            title={collapseLabel}
          >
            <Icon name={isCollapsed ? "panelOpen" : "panelClose"} />
          </button>
        </div>
      </div>

      <div className={styles.primaryAction}>
        <button
          id="historyNewChatBtn"
          type="button"
          className={styles.newChatButton}
          onClick={startNewChat}
          aria-label="New chat"
          title={isCollapsed ? "New chat" : undefined}
        >
          <Icon name="plus" />
          <span>New chat</span>
        </button>
      </div>

      <nav className={styles.nav} aria-label="Workspace">
        <button
          type="button"
          className={mode === "single" ? styles.navItemActive : styles.navItem}
          onClick={() => setMode("single")}
          aria-current={mode === "single" ? "page" : undefined}
          aria-label="Ask"
          title={isCollapsed ? "Ask" : undefined}
        >
          <Icon name="ask" />
          <span>Ask</span>
        </button>
        <button
          type="button"
          className={mode === "compare" ? styles.navItemActive : styles.navItem}
          onClick={() => setMode("compare")}
          aria-current={mode === "compare" ? "page" : undefined}
          aria-label="Compare"
          title={isCollapsed ? "Compare" : undefined}
        >
          <Icon name="compare" />
          <span>Compare</span>
        </button>
      </nav>

      <div className={styles.historyBlock} hidden={isCollapsed}>
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
          {filteredThreads.map((thread) => {
            const modeLabel = formatMode(thread.mode);
            const dateLabel =
              formatHistoryDateTime(thread.latestTimestamp) || "Date unavailable";

            return (
              <li key={thread.key}>
                <button
                  type="button"
                  className={
                    thread.sessionId === sessionId ? styles.historyItemActive : undefined
                  }
                  data-history-thread={thread.key}
                  onClick={() => onSelectThread(thread)}
                  title={thread.title}
                  aria-label={`${thread.title}. ${modeLabel}, ${dateLabel}`}
                  aria-current={thread.sessionId === sessionId ? "page" : undefined}
                >
                  <span className={styles.historyTitle} data-history-title>
                    {thread.title}
                  </span>
                  <small className={styles.historyMeta}>
                    <span>{modeLabel}</span>
                    <time dateTime={thread.latestTimestamp}>{dateLabel}</time>
                  </small>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      <button
        type="button"
        className={styles.profile}
        onClick={loggedIn ? onLogout : onLogin}
        disabled={!loggedIn && !onLogin}
        aria-label={loggedIn ? `Sign out ${userLabel}` : onLogin ? "Sign in" : "Guest account"}
        title={isCollapsed ? userLabel : undefined}
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

function Icon({ name }: { name: "plus" | "ask" | "compare" | "panelOpen" | "panelClose" }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {name === "plus" && (
        <>
          <path d="M12 5v14" />
          <path d="M5 12h14" />
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
      {name === "panelClose" && (
        <>
          <path d="M4 5h16v14H4z" />
          <path d="M9 5v14" />
          <path d="M15 9l-3 3 3 3" />
        </>
      )}
      {name === "panelOpen" && (
        <>
          <path d="M4 5h16v14H4z" />
          <path d="M9 5v14" />
          <path d="M12 9l3 3-3 3" />
        </>
      )}
    </svg>
  );
}
