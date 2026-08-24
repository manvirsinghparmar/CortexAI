import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WorkPage } from "../pages/WorkPage";
import { useWorkStore } from "../store/workStore";
import type { WorkEvent, WorkRun, WorkSession } from "../types";

const apiMocks = vi.hoisted(() => ({
  beginToolOAuth: vi.fn(),
  cancelWorkRun: vi.fn(),
  createToolConnection: vi.fn(),
  createWorkSession: vi.fn(),
  decideWorkApproval: vi.fn(),
  getLatestWorkRun: vi.fn(),
  getWorkApproval: vi.fn(),
  getWorkEvents: vi.fn(),
  getWorkRun: vi.fn(),
  getWorkSession: vi.fn(),
  listToolCatalog: vi.fn(),
  listToolConnections: vi.fn(),
  listWorkArtifacts: vi.fn(),
  listWorkSessions: vi.fn(),
  sendWorkInstruction: vi.fn(),
  startWorkRun: vi.fn(),
  streamWorkEvents: vi.fn(),
  testToolConnection: vi.fn(),
}));

vi.mock("../api/work", () => apiMocks);
vi.mock("../config/runtimeConfig", () => ({
  getRuntimeConfig: () => ({ workEnabled: true }),
}));
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    whoAmI: null,
    cognitoConfig: { enabled: false },
    loading: false,
    loggedIn: true,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));
vi.mock("../hooks/useSubscription", () => ({
  useSubscription: () => ({
    entitlements: {
      features: { work_enabled: true },
      limits: { max_work_credit_budget: 1_000_000 },
    },
  }),
}));
vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));
vi.mock("../subscription/accountMenuPresentation", () => ({
  getAccountMenuSubscriptionPresentation: () => ({
    planLabel: "Pro",
    billingActionLabel: "Manage plan",
    billingPastDue: false,
    billingDestination: null,
  }),
}));
vi.mock("../components/layout/Sidebar", () => ({ Sidebar: () => null }));
vi.mock("../components/layout/AccountMenu", () => ({ AccountMenu: () => null }));
vi.mock("../components/subscription/SubscriptionBanner", () => ({
  SubscriptionBanner: () => null,
}));
vi.mock("../components/work/WorkComposer", () => ({ WorkComposer: () => null }));
vi.mock("../components/work/WorkRail", () => ({ WorkRail: () => null }));
vi.mock("../components/work/WorkArtifacts", () => ({ WorkArtifacts: () => null }));
vi.mock("../components/work/WorkApproval", () => ({ WorkApproval: () => null }));

describe("WorkPage terminal event synchronization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const state = useWorkStore.getState();
    state.resetWorkspace();
    state.setSessions([]);
    state.setConnections([]);
    state.setToolCatalog([]);

    apiMocks.getWorkSession.mockResolvedValue(workSession());
    apiMocks.getLatestWorkRun.mockResolvedValue(workRun());
    apiMocks.getWorkRun.mockResolvedValue(
      workRun({
        status: "completed",
        completed_at: "2026-08-24T23:00:13Z",
        stop_reason: "end_turn",
      }),
    );
    apiMocks.listWorkSessions.mockResolvedValue([workSession()]);
    apiMocks.listToolCatalog.mockResolvedValue([]);
    apiMocks.listToolConnections.mockResolvedValue([]);
    apiMocks.listWorkArtifacts.mockResolvedValue([]);
    apiMocks.getWorkEvents.mockImplementation(async (_runId: string, afterSequence = 0) => {
      if (afterSequence === 12) {
        return {
          items: [
            workEvent(19, "agent_message", "The complete response arrived before refresh."),
            workEvent(23, "run_completed", "Work completed"),
          ],
          latest_sequence: 23,
        };
      }
      return {
        items: [workEvent(11, "progress", "Work is running")],
        latest_sequence: 11,
      };
    });
    apiMocks.streamWorkEvents.mockImplementation(
      async (
        _runId: string,
        _afterSequence: number,
        onEvent: (event: WorkEvent) => Promise<boolean | void>,
      ) => {
        await onEvent(workEvent(12, "progress", "Usage updated"));
      },
    );
  });

  afterEach(() => {
    cleanup();
    useWorkStore.getState().resetWorkspace();
  });

  it("loads remaining events before stopping when the refreshed run is already complete", async () => {
    render(
      <MemoryRouter initialEntries={["/work/work-session-1"]}>
        <Routes>
          <Route path="/work/:workSessionId" element={<WorkPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("The complete response arrived before refresh."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Cortex completed the requested work.")).not.toBeInTheDocument();
    expect(apiMocks.getWorkEvents).toHaveBeenCalledWith("run-1", 12);
    await waitFor(() => {
      expect(useWorkStore.getState().events.map((event) => event.sequence)).toEqual([
        11, 12, 19, 23,
      ]);
    });
  });
});

function workSession(): WorkSession {
  return {
    id: "work-session-1",
    session_id: "history-session-1",
    title: "Can you try again",
    status: "running",
    agent_provider: "fake",
    created_at: "2026-08-24T23:00:00Z",
    updated_at: "2026-08-24T23:00:00Z",
    latest_run_status: "running",
  };
}

function workRun(overrides: Partial<WorkRun> = {}): WorkRun {
  return {
    id: "run-1",
    work_session_id: "work-session-1",
    request_id: "request-1",
    instruction: "Can you try again",
    status: "running",
    provider: "fake",
    max_credit_budget: 1_000_000,
    reserved_credits: 1_000_000,
    actual_credits: 39_651,
    configuration_snapshot: { web_enabled: false },
    usage_snapshot: {},
    stop_reason: null,
    error_code: null,
    error_message: null,
    started_at: "2026-08-24T23:00:04Z",
    completed_at: null,
    created_at: "2026-08-24T23:00:04Z",
    updated_at: "2026-08-24T23:00:12Z",
    ...overrides,
  };
}

function workEvent(sequence: number, type: string, displayMessage: string): WorkEvent {
  return {
    id: `event-${sequence}`,
    sequence,
    type,
    display_message: displayMessage,
    payload: {},
    created_at: "2026-08-24T23:00:13Z",
  };
}
