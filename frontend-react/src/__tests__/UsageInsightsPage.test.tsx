import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UsageInsightsPage } from "../pages/UsageInsightsPage";
import { useChatStore } from "../store/chatStore";
import type { UsageSummary } from "../types";

interface MockUsageState {
  summary: UsageSummary | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const hookMocks = vi.hoisted(() => ({
  usageState: {
    current: {
      summary: null as UsageSummary | null,
      loading: true as boolean,
      error: null as string | null,
      reload: vi.fn(),
    } satisfies MockUsageState,
  },
  loadHistory: vi.fn(),
  clearHistory: vi.fn(),
  removeThread: vi.fn(),
  cancel: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  toggleTheme: vi.fn(),
}));

vi.mock("../hooks/useUsageSummary", () => ({
  useUsageSummary: () => hookMocks.usageState.current,
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    whoAmI: null,
    cognitoConfig: { enabled: false },
    loading: false,
    loggedIn: false,
    login: hookMocks.login,
    logout: hookMocks.logout,
  }),
}));

vi.mock("../hooks/useHistory", () => ({
  useHistory: () => ({
    load: hookMocks.loadHistory,
    clear: hookMocks.clearHistory,
    removeThread: hookMocks.removeThread,
  }),
}));

vi.mock("../hooks/useChat", () => ({
  useChat: () => ({ cancel: hookMocks.cancel }),
}));

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: hookMocks.toggleTheme }),
}));

describe("UsageInsightsPage states", () => {
  beforeEach(() => {
    hookMocks.usageState.current = {
      summary: null,
      loading: true,
      error: null,
      reload: vi.fn(),
    };
    resetStore();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    resetStore();
  });

  it("renders the Step 2 loading skeleton state", () => {
    renderPage();

    expect(screen.getByLabelText("Loading usage insights")).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("renders backend-driven KPI cards after usage data loads", () => {
    hookMocks.usageState.current = {
      summary: usageSummary(),
      loading: false,
      error: null,
      reload: vi.fn(),
    };

    renderPage();

    expect(
      screen.getByLabelText("TOTAL TOKENS 2.84M 18.4% vs prev 30d"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("REQUESTS 1,336 across 312 sessions"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("AVG LATENCY 4.6s p95 8.1s \u00b7 fastest 1.4s"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("AVG COST / REQ $0.0091 $12.16 total spend"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Usage details pending")).toBeInTheDocument();
  });

  it("renders the empty model activity state", () => {
    hookMocks.usageState.current = {
      summary: emptyUsageSummary(),
      loading: false,
      error: null,
      reload: vi.fn(),
    };

    renderPage();

    expect(screen.getByLabelText("TOTAL TOKENS 0 \u2014")).toBeInTheDocument();
    expect(screen.getByLabelText("AVG LATENCY \u2014 \u2014")).toBeInTheDocument();
    expect(screen.getByText("No model activity yet for this period")).toBeInTheDocument();
  });

  it("renders an inline retry action for errors", async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    hookMocks.usageState.current = {
      summary: null,
      loading: false,
      error: "Reporting service unavailable",
      reload,
    };

    renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent("Usage data could not load.");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });
});

function renderPage() {
  render(
    <MemoryRouter>
      <UsageInsightsPage />
    </MemoryRouter>,
  );
}

function emptyUsageSummary(): UsageSummary {
  return usageSummary({
    totalTokens: 0,
    totalRequests: 0,
    totalSessions: 0,
    avgLatencyMs: 0,
    p95LatencyMs: 0,
    minLatencyMs: 0,
    avgCostPerRequest: 0,
    totalSpend: 0,
    tokensDeltaPct: 0,
    smartRoutedTotal: 0,
    models: [],
    sessionModes: { askOnly: 0, compareOnly: 0, mixed: 0 },
    switchedMidSession: 0,
    activityDaily: [],
  });
}

function usageSummary(overrides: Partial<UsageSummary> = {}): UsageSummary {
  return {
    period: { from: "2026-06-01", to: "2026-06-30", label: "Last 30 days" },
    totalTokens: 2840000,
    totalRequests: 1336,
    totalSessions: 312,
    avgLatencyMs: 4600,
    p95LatencyMs: 8100,
    minLatencyMs: 1400,
    avgCostPerRequest: 0.0091,
    totalSpend: 12.16,
    tokensDeltaPct: 18.4,
    smartRoutedTotal: 720,
    models: [
      {
        provider: "openai",
        modelId: "gpt-5.4-mini",
        displayName: "GPT-5.4 Mini",
        replies: 512,
        viaSmart: 470,
      },
    ],
    sessionModes: { askOnly: 168, compareOnly: 96, mixed: 48 },
    switchedMidSession: 48,
    activityDaily: [{ date: "2026-06-30", tokens: 200000 }],
    ...overrides,
  };
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}
