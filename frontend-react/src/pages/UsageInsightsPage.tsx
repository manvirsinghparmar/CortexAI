import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHistory } from "../api/history";
import { AccountMenu } from "../components/layout/AccountMenu";
import { Sidebar } from "../components/layout/Sidebar";
import { CortexIcon } from "../components/shared/CortexIcon";
import { buildHistoryThreads } from "../history/historyThreads";
import { useAuth } from "../hooks/useAuth";
import { useChat } from "../hooks/useChat";
import { useHistory } from "../hooks/useHistory";
import { useTheme } from "../hooks/useTheme";
import { useChatStore } from "../store/chatStore";
import type { ChatMode, HistoryThread } from "../types";
import styles from "./UsageInsightsPage.module.css";

export function UsageInsightsPage() {
  const navigate = useNavigate();
  const { whoAmI, cognitoConfig, loading: authLoading, loggedIn, login, logout } = useAuth();
  const { load: loadHistory } = useHistory();
  const { cancel } = useChat();
  const { theme, toggleTheme } = useTheme();
  const hydrateFromHistoryThread = useChatStore((s) => s.hydrateFromHistoryThread);
  const setMode = useChatStore((s) => s.setMode);
  const startNewChat = useChatStore((s) => s.startNewChat);
  const setHistory = useChatStore((s) => s.setHistory);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
  const setError = useChatStore((s) => s.setError);
  const authEnabled = cognitoConfig?.enabled ?? false;

  useEffect(() => {
    if (!authLoading) void loadHistory({ restoreActiveTranscript: false });
  }, [authLoading, loadHistory]);

  const openChatMode = (nextMode: ChatMode) => {
    setMode(nextMode);
    navigate("/");
  };

  const handleSelectHistoryThread = async (thread: HistoryThread) => {
    try {
      const entries = thread.sessionId
        ? await fetchHistory(500, thread.sessionId)
        : thread.entries;
      const completeThread = buildHistoryThreads(entries)[0] ?? thread;
      hydrateFromHistoryThread(completeThread);
      navigate("/");
    } catch (historyError) {
      setError(historyError instanceof Error ? historyError.message : "Failed to load chat history");
      navigate("/");
    }
  };

  const handleLogout = () => {
    cancel();
    startNewChat();
    setHistory([]);
    setHistorySearch("");
    void logout();
  };

  return (
    <div className={styles.layout}>
      <Sidebar
        onSelectThread={(thread) => void handleSelectHistoryThread(thread)}
        activeView="usage"
        onNavigateChat={openChatMode}
        onNavigateUsage={() => navigate("/usage")}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? login : undefined}
        onLogout={authEnabled ? handleLogout : undefined}
      />

      <main className={styles.main}>
        <header className={styles.header}>
          <button
            type="button"
            className={styles.mobileBackButton}
            aria-label="Back to chat"
            onClick={() => navigate("/")}
          >
            <CortexIcon name="chevron-left" size={16} strokeWidth={2} />
          </button>
          <div className={styles.titleBlock}>
            <h1>Usage &amp; insights</h1>
            <p className={styles.desktopSubtitle}>All models · last 30 days</p>
            <p className={styles.mobileSubtitle}>Last 30 days</p>
          </div>
          <div className={styles.actions} aria-label="Usage controls">
            <button type="button" className={styles.periodButton} aria-label="Select usage period">
              <span className={styles.periodDesktopLabel}>Last 30 days</span>
              <span className={styles.periodMobileLabel}>30d</span>
              <CortexIcon name="chevron-down" size={14} strokeWidth={2} />
            </button>
            <button type="button" className={styles.exportButton} aria-label="Export usage">
              <CortexIcon name="download" size={15} />
              <span>Export</span>
            </button>
            <div className={styles.mobileAccountMenu}>
              <AccountMenu
                authEnabled={authEnabled}
                loggedIn={loggedIn}
                onLogin={authEnabled ? login : undefined}
                onLogout={handleLogout}
                theme={theme}
                onToggleTheme={toggleTheme}
              />
            </div>
          </div>
        </header>
        <section className={styles.body} aria-label="Usage dashboard content" />
      </main>
    </div>
  );
}
