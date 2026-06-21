import { useMemo, useState } from "react";
import { formatHistoryDateTime } from "../../history/historyDate";
import { buildHistoryThreads, filterHistoryThreads } from "../../history/historyThreads";
import { useChatStore } from "../../store/chatStore";
import { useHistory } from "../../hooks/useHistory";
import type { HistoryThread, WhoAmIResponse } from "../../types";
import { CortexIcon } from "../shared/CortexIcon";
import brandMarkUrl from "../../assets/brand/brand-mark.svg";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  onSelectThread: (thread: HistoryThread) => void;
  whoAmI?: WhoAmIResponse | null;
  loggedIn?: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
}

interface HistoryDateGroup {
  key: string;
  label: string;
  threads: HistoryThread[];
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
  const historyGroups = useMemo(() => groupHistoryThreads(filteredThreads), [filteredThreads]);

  const userLabel = whoAmI?.user_id ?? (loggedIn ? "Signed in" : "Guest");
  const planLabel = whoAmI?.plan_tier ?? (loggedIn ? "Session active" : "Local session");
  const sessionLabel = sessionId ? formatSessionId(sessionId) : userLabel;
  const sessionStatus = sessionId || loggedIn ? "Session active" : planLabel;

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
          <div className={styles.brandLockup}>
            <img className={styles.brandMark} src={brandMarkUrl} alt="" aria-hidden="true" />
            <div className={styles.brandText} hidden={isCollapsed}>
              <h1>CortexAI</h1>
              <p>LLM GATEWAY</p>
            </div>
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
            <CortexIcon name={isCollapsed ? "expand-sidebar" : "collapse-sidebar"} />
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
          <CortexIcon name="new-chat" />
          <span>New chat</span>
          <span className={styles.commandChip} aria-hidden="true">
            ⌘K
          </span>
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
          <CortexIcon name="ask" />
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
          <CortexIcon name="compare" />
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
        <div className={styles.historySearchWrap}>
          <CortexIcon name="search" />
          <input
            id="historySearch"
            className={styles.historySearch}
            value={historySearch}
            onChange={(event) => setHistorySearch(event.target.value)}
            placeholder="Search history"
            aria-label="Search history"
          />
        </div>
        <ul className={styles.historyList}>
          {historyGroups.map((group) => (
            <li key={group.key} className={styles.historyGroup}>
              <div className={styles.historyGroupLabel}>{group.label}</div>
              <ul className={styles.historyGroupItems}>
                {group.threads.map((thread) => {
                  const modeLabel = formatMode(thread.mode);
                  const timeLabel = formatHistoryTime(thread.latestTimestamp);
                  const dateTimeLabel = formatHistoryDateTime(thread.latestTimestamp);
                  const modeClassName = [
                    styles.modeTag,
                    thread.mode === "compare"
                      ? styles.modeTagCompare
                      : thread.mode === "single"
                        ? styles.modeTagAsk
                        : styles.modeTagMixed,
                  ].join(" ");

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
                        aria-label={`${thread.title}. ${modeLabel}, ${
                          dateTimeLabel || "Date unavailable"
                        }`}
                        aria-current={thread.sessionId === sessionId ? "page" : undefined}
                      >
                        <span className={styles.historyTitle} data-history-title>
                          {thread.title}
                        </span>
                        <small className={styles.historyMeta}>
                          <span className={modeClassName}>{modeLabel.toUpperCase()}</span>
                          <time dateTime={thread.latestTimestamp}>
                            {timeLabel || "Date unavailable"}
                          </time>
                        </small>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
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
        <span className={styles.sessionDot} aria-hidden="true">
          <span />
        </span>
        <span className={styles.profileText}>
          <strong>{sessionLabel}</strong>
          <span>{sessionStatus}</span>
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

function groupHistoryThreads(threads: HistoryThread[]): HistoryDateGroup[] {
  const groups = new Map<string, HistoryDateGroup>();

  for (const thread of threads) {
    const label = formatHistoryGroupLabel(thread.latestTimestamp);
    const key = label || "unknown";
    const group = groups.get(key) ?? { key, label: label || "Date unavailable", threads: [] };
    group.threads.push(thread);
    groups.set(key, group);
  }

  return [...groups.values()];
}

function formatHistoryGroupLabel(value: string, now = new Date()): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "";

  const date = new Date(timestamp);
  if (isSameLocalDate(date, now)) return "Today";

  const options: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
  };
  if (date.getFullYear() !== now.getFullYear()) options.year = "numeric";

  return date.toLocaleDateString(undefined, options);
}

function formatHistoryTime(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "";

  return new Date(timestamp).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function formatSessionId(value: string): string {
  const normalized = value.trim();
  if (normalized.length <= 14) return normalized;
  return `${normalized.slice(0, 8)}...${normalized.slice(-4)}`;
}
