import { useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHistory } from "../../api/history";
import brandMarkUrl from "../../assets/brand/brand-mark.svg";
import { buildHistoryThreads } from "../../history/historyThreads";
import { useHistory } from "../../hooks/useHistory";
import { useTheme } from "../../hooks/useTheme";
import { useChatStore } from "../../store/chatStore";
import type { ChatMode, HistoryThread, WhoAmIResponse } from "../../types";
import { AccountMenu } from "../layout/AccountMenu";
import { Sidebar } from "../layout/Sidebar";
import { CortexIcon } from "../shared/CortexIcon";
import styles from "./SubscriptionPageShell.module.css";

interface SubscriptionPageShellProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  authLoading: boolean;
  authEnabled: boolean;
  loggedIn: boolean;
  whoAmI: WhoAmIResponse | null;
  onLogin?: () => void;
  onLogout: () => void | Promise<void>;
  planLabel?: string;
  billingActionLabel?: string;
  billingPastDue?: boolean;
  billingDestination?: "/pricing" | "/account/billing";
}

export function SubscriptionPageShell({
  title,
  subtitle,
  children,
  authLoading,
  authEnabled,
  loggedIn,
  whoAmI,
  onLogin,
  onLogout,
  planLabel,
  billingActionLabel,
  billingPastDue,
  billingDestination = "/account/billing",
}: SubscriptionPageShellProps) {
  const navigate = useNavigate();
  const { load: loadHistory } = useHistory();
  const { theme, toggleTheme } = useTheme();
  const hydrateFromHistoryThread = useChatStore((state) => state.hydrateFromHistoryThread);
  const setMode = useChatStore((state) => state.setMode);
  const startNewChat = useChatStore((state) => state.startNewChat);
  const setHistory = useChatStore((state) => state.setHistory);
  const setHistorySearch = useChatStore((state) => state.setHistorySearch);
  const setError = useChatStore((state) => state.setError);

  useEffect(() => {
    if (!authLoading) void loadHistory({ restoreActiveTranscript: false });
  }, [authLoading, loadHistory]);

  const openChatMode = (mode: ChatMode) => {
    setMode(mode);
    navigate("/");
  };

  const handleSelectHistoryThread = async (thread: HistoryThread) => {
    try {
      const entries = thread.sessionId ? await fetchHistory(500, thread.sessionId) : thread.entries;
      const completeThread = buildHistoryThreads(entries)[0] ?? thread;
      hydrateFromHistoryThread(completeThread);
      navigate("/");
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : "Failed to load chat history");
      navigate("/");
    }
  };

  const handleLogout = () => {
    startNewChat();
    setHistory([]);
    setHistorySearch("");
    void onLogout();
  };

  const accountMenu = (
    <AccountMenu
      authEnabled={authEnabled}
      loggedIn={loggedIn}
      onLogin={authEnabled ? onLogin : undefined}
      onLogout={handleLogout}
      planLabel={planLabel}
      billingActionLabel={billingActionLabel}
      billingPastDue={billingPastDue}
      onBilling={planLabel ? () => navigate(billingDestination) : undefined}
      onModels={() => navigate("/models")}
      onUsageInsights={() => navigate("/usage")}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  );

  return (
    <div className={styles.layout}>
      <Sidebar
        onSelectThread={(thread) => void handleSelectHistoryThread(thread)}
        activeView="account"
        onNavigateChat={openChatMode}
        onNavigateUsage={() => navigate("/usage")}
        onNavigateModels={() => navigate("/models")}
        whoAmI={whoAmI}
        loggedIn={loggedIn}
        onLogin={authEnabled ? onLogin : undefined}
      />

      <main className={styles.main}>
        <header className={styles.desktopHeader}>
          <button type="button" className={styles.brandButton} onClick={() => navigate("/")}>
            <img src={brandMarkUrl} alt="" aria-hidden="true" />
            <span>CortexAI</span>
          </button>
          <div className={styles.desktopTitle}>
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
          {accountMenu}
        </header>

        <header className={styles.mobileHeader}>
          <button
            type="button"
            className={styles.backButton}
            aria-label="Back to chat"
            onClick={() => navigate("/")}
          >
            <CortexIcon name="chevron-left" size={18} strokeWidth={2} />
          </button>
          <div className={styles.mobileTitle}>
            <strong>{title}</strong>
            <span>{subtitle}</span>
          </div>
          {accountMenu}
        </header>

        <div className={styles.content}>{children}</div>
      </main>
    </div>
  );
}
