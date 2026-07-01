import { useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHistory } from "../api/history";
import { AccountMenu } from "../components/layout/AccountMenu";
import { Sidebar } from "../components/layout/Sidebar";
import { CortexIcon, type CortexIconName } from "../components/shared/CortexIcon";
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
          ) : summary ? (
            <UsageDashboard summary={summary} showModelEmpty={empty} />
          ) : (
            <section className={styles.readyState} aria-label="Usage summary loaded" />
          )}
        </section>
      </main>
    </div>
  );
}

function UsageDashboard({
  summary,
  showModelEmpty,
}: {
  summary: UsageSummary;
  showModelEmpty: boolean;
}) {
  return (
    <section className={styles.dashboard} aria-label="Usage summary loaded">
      <KpiRow summary={summary} />
      {showModelEmpty ? (
        <UsageEmptyState />
      ) : (
        <section className={styles.readyState} aria-label="Usage details pending" />
      )}
    </section>
  );
}

function KpiRow({ summary }: { summary: UsageSummary }) {
  const cards = buildKpiCards(summary);

  return (
    <section className={styles.kpiGrid} aria-label="Usage key metrics">
      {cards.map((card) => (
        <article className={styles.kpiCard} aria-label={card.ariaLabel} key={card.key}>
          <div className={styles.kpiHeader}>
            <span className={`${styles.kpiTile} ${card.accent ? styles.kpiTileAccent : ""}`}>
              <CortexIcon name={card.icon} size={16} strokeWidth={1.85} />
            </span>
            <span className={styles.kpiLabel}>{card.label}</span>
          </div>
          <div className={styles.kpiFigure}>
            {card.figure}
            {card.suffix ? <span className={styles.kpiSuffix}>{card.suffix}</span> : null}
          </div>
          <div
            className={`${styles.kpiSubnote} ${
              card.positiveTrend ? styles.kpiSubnotePositive : ""
            }`}
          >
            {card.subnote}
          </div>
        </article>
      ))}
    </section>
  );
}

interface KpiCardConfig {
  key: string;
  label: string;
  icon: CortexIconName;
  accent?: boolean;
  figure: string;
  suffix?: string;
  subnote: ReactNode;
  ariaLabel: string;
  positiveTrend?: boolean;
}

function buildKpiCards(summary: UsageSummary): KpiCardConfig[] {
  const hasUsage = summary.totalRequests > 0 || summary.totalTokens > 0;
  const tokenValue = formatCompactNumber(summary.totalTokens);
  const tokenDelta = hasUsage ? formatPercent(summary.tokensDeltaPct) : DASH;
  const tokenDirection = summary.tokensDeltaPct < 0 ? "down" : "up";
  const latencyValue = hasUsage ? formatLatency(summary.avgLatencyMs) : DASH;
  const latencySub = hasUsage
    ? `p95 ${formatLatency(summary.p95LatencyMs)} \u00b7 fastest ${formatLatency(summary.minLatencyMs)}`
    : DASH;
  const costValue = hasUsage ? formatCost(summary.avgCostPerRequest, 4) : DASH;
  const spendSub = hasUsage ? `${formatCost(summary.totalSpend, 2)} total spend` : DASH;

  return [
    {
      key: "tokens",
      label: "TOTAL TOKENS",
      icon: "tokens",
      accent: true,
      figure: tokenValue.figure,
      suffix: tokenValue.suffix,
      subnote: hasUsage ? (
        <>
          <TrendIcon direction={tokenDirection} />
          {tokenDelta} vs prev 30d
        </>
      ) : (
        DASH
      ),
      ariaLabel: `TOTAL TOKENS ${tokenValue.figure}${tokenValue.suffix ?? ""} ${
        hasUsage ? `${tokenDelta} vs prev 30d` : DASH
      }`,
      positiveTrend: hasUsage && summary.tokensDeltaPct >= 0,
    },
    {
      key: "requests",
      label: "REQUESTS",
      icon: "swap",
      figure: formatInteger(summary.totalRequests),
      subnote: `across ${formatInteger(summary.totalSessions)} sessions`,
      ariaLabel: `REQUESTS ${formatInteger(summary.totalRequests)} across ${formatInteger(
        summary.totalSessions,
      )} sessions`,
    },
    {
      key: "latency",
      label: "AVG LATENCY",
      icon: "latency",
      figure: latencyValue,
      subnote: latencySub,
      ariaLabel: `AVG LATENCY ${latencyValue} ${latencySub}`,
    },
    {
      key: "cost",
      label: "AVG COST / REQ",
      icon: "cost",
      figure: costValue,
      subnote: spendSub,
      ariaLabel: `AVG COST / REQ ${costValue} ${spendSub}`,
    },
  ];
}

function TrendIcon({ direction }: { direction: "up" | "down" }) {
  return (
    <svg
      className={direction === "down" ? styles.trendIconDown : styles.trendIcon}
      width="9"
      height="9"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 5l8 13H4z" />
    </svg>
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

const DASH = "\u2014";

function formatCompactNumber(value: number): { figure: string; suffix?: string } {
  if (!Number.isFinite(value) || value <= 0) return { figure: "0" };
  if (value >= 1_000_000) return { figure: trimNumber(value / 1_000_000, 2), suffix: "M" };
  if (value >= 1_000) return { figure: trimNumber(value / 1_000, 1), suffix: "K" };
  return { figure: formatInteger(value) };
}

function trimNumber(value: number, maximumFractionDigits: number): string {
  return value.toLocaleString("en-US", {
    maximumFractionDigits,
    minimumFractionDigits: maximumFractionDigits,
  }).replace(/\.0+$/, "");
}

function formatInteger(value: number): string {
  if (!Number.isFinite(value)) return "0";
  return Math.round(value).toLocaleString("en-US");
}

function formatLatency(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return DASH;
  return `${(ms / 1000).toLocaleString("en-US", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
  })}s`;
}

function formatCost(value: number, fractionDigits: number): string {
  if (!Number.isFinite(value) || value < 0) return DASH;
  return `$${value.toLocaleString("en-US", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  })}`;
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "0%";
  const normalized = Math.abs(value);
  return `${normalized.toLocaleString("en-US", {
    maximumFractionDigits: 1,
    minimumFractionDigits: Number.isInteger(normalized) ? 0 : 1,
  })}%`;
}

function isUsageSummaryEmpty(summary: UsageSummary): boolean {
  return summary.totalRequests === 0 || summary.models.length === 0;
}
