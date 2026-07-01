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

  it("renders the empty model activity state", () => {
    hookMocks.usageState.current = {
      summary: emptyUsageSummary(),
      loading: false,
      error: null,
      reload: vi.fn(),
    };

    renderPage();

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
  return {
    period: { from: "2026-06-01", to: "2026-06-30", label: "Last 30 days" },
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
  };
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}
