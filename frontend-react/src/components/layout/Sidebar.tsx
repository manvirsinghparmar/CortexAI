import { useMemo } from "react";
import { useChatStore } from "../../store/chatStore";
import { useHistory } from "../../hooks/useHistory";
import type { HistoryEntry } from "../../types";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  onSelectEntry: (entry: HistoryEntry) => void;
}

export function Sidebar({ onSelectEntry }: SidebarProps) {
  const history = useChatStore((s) => s.history);
  const historySearch = useChatStore((s) => s.historySearch);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
  const setHistory = useChatStore((s) => s.setHistory);
  const sessionId = useChatStore((s) => s.sessionId);
  const { clear } = useHistory();

  const filtered = useMemo(() => {
    const q = historySearch.trim().toLowerCase();
    if (!q) return history;
    return history.filter(
      (e) =>
        e.prompt.toLowerCase().includes(q) || e.response.toLowerCase().includes(q),
    );
  }, [history, historySearch]);

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
    <aside className={styles.sidebar} aria-label="Chat history">
      <div className={styles.sidebarHeader}>
        <div className={styles.titleRow}>
          <span className={styles.title}>History</span>
        </div>
        <div className={styles.actions}>
          <button className={styles.newChatBtn} onClick={handleNewChat} title="Start a new chat">
            <svg
              className={styles.newChatIcon}
              viewBox="0 0 24 24"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 20H5a1 1 0 0 1-1-1v-7" />
              <path d="M20.65 7.35a2.1 2.1 0 0 0-2.97-2.97L8 14.06V18h3.94l8.71-8.65Z" />
            </svg>
            <span>New chat</span>
          </button>
          <button className={styles.clearBtn} onClick={handleClearAll} title="Clear all history">
            Clear
          </button>
        </div>
      </div>

      <div className={styles.searchWrap}>
        <span className={styles.searchIcon} aria-hidden="true">&#128269;</span>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search history"
          aria-label="Search history"
          value={historySearch}
          onChange={(e) => setHistorySearch(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>Chat</div>
          <p>No history yet.<br />Send a prompt to get started.</p>
        </div>
      ) : (
        <ul className={styles.list} role="list">
          {filtered.map((entry) => (
            <li key={entry.id} className={styles.listItem} role="listitem">
              <button
                className={styles.entryBtn}
                onClick={() => onSelectEntry(entry)}
                title={entry.prompt}
              >
                <span className={styles.entryPrompt}>{entry.prompt}</span>
                <span className={styles.entryMeta}>
                  {new Date(entry.timestamp).toLocaleDateString()} · {entry.provider}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
