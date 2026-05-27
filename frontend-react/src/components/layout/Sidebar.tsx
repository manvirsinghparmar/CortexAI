import { useMemo } from "react";
import { useChatStore } from "../../store/chatStore";
import { useHistory } from "../../hooks/useHistory";
import type { HistoryEntry, WhoAmIResponse } from "../../types";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  onSelectEntry: (entry: HistoryEntry) => void;
  whoAmI?: WhoAmIResponse | null;
  loggedIn?: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
}

export function Sidebar({
  onSelectEntry,
  whoAmI,
  loggedIn,
  onLogin,
  onLogout,
}: SidebarProps) {
  const history = useChatStore((s) => s.history);
  const setHistory = useChatStore((s) => s.setHistory);
  const sessionId = useChatStore((s) => s.sessionId);
  const mode = useChatStore((s) => s.mode);
  const setMode = useChatStore((s) => s.setMode);
  const { clear } = useHistory();

  const latest = useMemo(() => history.slice(0, 6), [history]);
  const userLabel = whoAmI?.user_id ?? (mode === "single" ? "Alex Rivera" : "Alex Chen");
  const planLabel = whoAmI?.plan_tier ?? (mode === "single" ? "Pro Plan" : loggedIn ? "Pro Plan" : "Guest");

  const handleClearAll = async () => {
    if (!window.confirm("Clear all chat history?")) return;
    await clear(sessionId ?? undefined);
    setHistory([]);
  };

  const handleNewChat = () => {
    useChatStore.setState({
      prompt: "",
      responses: [],
      streamingText: "",
      streaming: false,
      error: null,
    });
  };

  return (
    <aside className={styles.sidebar} aria-label="Primary navigation">
      <div className={styles.brand}>
        <h1>CortexAI</h1>
        <p>{mode === "single" ? "Technical Gateway" : "Gateway"}</p>
      </div>

      {mode === "single" && (
        <button type="button" className={styles.newChatButton} onClick={handleNewChat}>
          <span aria-hidden="true">+</span>
          New Chat
        </button>
      )}

      <nav className={styles.nav} aria-label="Workspace">
        <button
          type="button"
          className={mode === "single" ? styles.navItemActiveLight : styles.navItem}
          onClick={handleNewChat}
        >
          <Icon name="history" />
          <span>History</span>
        </button>
        <button type="button" className={styles.navItem}>
          <Icon name="analytics" />
          <span>Analytics</span>
        </button>
        <button
          type="button"
          className={mode === "compare" ? styles.navItemActive : styles.navItem}
          onClick={() => setMode("compare")}
        >
          <Icon name="models" />
          <span>Models</span>
        </button>
        <button type="button" className={styles.navItem}>
          <Icon name="key" />
          <span>API Keys</span>
        </button>
      </nav>

      {latest.length > 0 && (
        <div className={styles.historyBlock}>
          <div className={styles.historyHeader}>
            <span>Recent</span>
            <button type="button" onClick={handleClearAll}>
              Clear
            </button>
          </div>
          <ul className={styles.historyList}>
            {latest.map((entry) => (
              <li key={entry.id}>
                <button type="button" onClick={() => onSelectEntry(entry)} title={entry.prompt}>
                  <span>{entry.prompt}</span>
                  <small>{entry.provider}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className={styles.profile}
        onClick={loggedIn ? onLogout : onLogin}
        disabled={!loggedIn && !onLogin}
      >
        <span className={styles.avatar} aria-hidden="true">
          {(userLabel[0] ?? "A").toUpperCase()}
        </span>
        <span className={styles.profileText}>
          <strong>{userLabel}</strong>
          <span>{planLabel}</span>
        </span>
      </button>
    </aside>
  );
}

function Icon({ name }: { name: "history" | "analytics" | "models" | "key" }) {
  const paths = {
    history: (
      <>
        <path d="M3 12a9 9 0 1 0 3-6.7" />
        <path d="M3 4v5h5" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    analytics: (
      <>
        <path d="M5 19V9" />
        <path d="M12 19V5" />
        <path d="M19 19v-7" />
      </>
    ),
    models: (
      <>
        <path d="M8 3h8l1 4 4 1v8l-4 1-1 4H8l-1-4-4-1V8l4-1 1-4Z" />
        <path d="M9 12h6" />
        <path d="M12 9v6" />
      </>
    ),
    key: (
      <>
        <circle cx="7.5" cy="12.5" r="3.5" />
        <path d="M11 12.5h10" />
        <path d="M17 12.5v3" />
        <path d="M20 12.5v2" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
