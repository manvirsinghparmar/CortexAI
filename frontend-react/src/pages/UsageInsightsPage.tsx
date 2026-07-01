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
import { useUsageSummary } from "../hooks/useUsageSummary";
import { useChatStore } from "../store/chatStore";
import type { ChatMode, HistoryThread, UsageSummary } from "../types";
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
  const { summary, loading: usageLoading, error: usageError, reload } = useUsageSummary();
  const authEnabled = cognitoConfig?.enabled ?? false;
  const periodLabel = summary?.period.label ?? "Last 30 days";
  const empty = summary ? isUsageSummaryEmpty(summary) : false;

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
            <p className={styles.desktopSubtitle}>
              All models <span aria-hidden="true">&middot;</span> {periodLabel.toLowerCase()}
            </p>
            <p className={styles.mobileSubtitle}>{periodLabel}</p>
          </div>
          <div className={styles.actions} aria-label="Usage controls">
            <button type="button" className={styles.periodButton} aria-label="Select usage period">
              <span className={styles.periodDesktopLabel}>{periodLabel}</span>
              <span className={styles.periodMobileLabel}>
                {periodLabel === "Last 30 days" ? "30d" : "Period"}
              </span>
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
                onUsageInsights={() => navigate("/usage")}
              />
            </div>
          </div>
        </header>
        <section className={styles.body} aria-label="Usage dashboard content">
          {usageLoading ? (
            <UsageLoadingState />
          ) : usageError ? (
            <UsageErrorState message={usageError} onRetry={reload} />
          ) : empty ? (
            <UsageEmptyState />
          ) : (
            <section className={styles.readyState} aria-label="Usage summary loaded" />
          )}
        </section>
      </main>
    </div>
  );
}

function UsageLoadingState() {
  return (
    <section className={styles.loadingState} aria-busy="true" aria-label="Loading usage insights">
      <span className={styles.srOnly}>Loading usage insights</span>
      <div className={styles.skeletonKpis} aria-hidden="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className={styles.skeletonCard} key={index}>
            <span className={`${styles.skeletonBlock} ${styles.skeletonTile}`} />
            <span className={`${styles.skeletonBlock} ${styles.skeletonFigure}`} />
            <span className={`${styles.skeletonBlock} ${styles.skeletonCaption}`} />
          </div>
        ))}
      </div>
      <div className={styles.skeletonPanels} aria-hidden="true">
        <div className={`${styles.skeletonPanel} ${styles.skeletonPanelWide}`}>
          <span className={`${styles.skeletonBlock} ${styles.skeletonHeader}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonRow}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonRowShort}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonRow}`} />
        </div>
        <div className={styles.skeletonPanel}>
          <span className={`${styles.skeletonBlock} ${styles.skeletonHeader}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonBar}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonRowShort}`} />
          <span className={`${styles.skeletonBlock} ${styles.skeletonRowShort}`} />
        </div>
      </div>
      <div className={styles.skeletonPanel} aria-hidden="true">
        <span className={`${styles.skeletonBlock} ${styles.skeletonHeader}`} />
        <span className={`${styles.skeletonBlock} ${styles.skeletonChart}`} />
      </div>
    </section>
  );
}

function UsageEmptyState() {
  return (
    <section className={styles.statePanel} aria-live="polite">
      <p>No model activity yet for this period</p>
    </section>
  );
}

function UsageErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <section className={styles.statePanel} role="alert">
      <div>
        <p className={styles.stateTitle}>Usage data could not load.</p>
        <p className={styles.stateText}>{message}</p>
      </div>
      <button type="button" className={styles.retryButton} onClick={onRetry}>
        Retry
      </button>
    </section>
  );
}

function isUsageSummaryEmpty(summary: UsageSummary): boolean {
  return summary.totalRequests === 0 || summary.models.length === 0;
}
