import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "../components/layout/Sidebar";
import { useChatStore } from "../store/chatStore";
import type { HistoryEntry, HistoryThread } from "../types";

describe("Sidebar", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetStore();
  });

  it("preserves mode navigation, active session, history search, and thread selection", async () => {
    const user = userEvent.setup();
    const onSelectThread = vi.fn<(thread: HistoryThread) => void>();
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
      mode: "single",
    });

    render(<Sidebar onSelectThread={onSelectThread} />);

    expect(screen.getByRole("heading", { name: "CortexAI" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "Usage" })).not.toHaveAttribute(
      "aria-current",
    );
    const activeThread = screen.getByRole("button", { name: /Quarterly planning\. Ask,/ });
    expect(activeThread).toHaveAttribute("aria-current", "page");
    expect(activeThread).toHaveAccessibleName(
      /Quarterly planning\. Ask,/,
    );
    expect(activeThread.querySelector("[data-history-title]")).toHaveTextContent(
      "Quarterly planning",
    );
    expect(activeThread.closest("li")?.querySelector("small")).toHaveTextContent(/^ASK/);
    expect(activeThread).not.toHaveTextContent("2 turns");
    expect(activeThread).not.toHaveTextContent("gpt-5.1");
    const timestamps = [...document.querySelectorAll("time")];
    expect(timestamps).toHaveLength(2);
    expect(
      timestamps.some(
        (timestamp) => timestamp.dateTime === "2026-06-10T11:00:00Z",
      ),
    ).toBe(true);

    await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(useChatStore.getState().mode).toBe("compare");

    await user.type(screen.getByRole("textbox", { name: "Search history" }), "vendors");
    expect(screen.queryByText("Quarterly planning")).not.toBeInTheDocument();
    const compareThread = screen.getByRole("button", { name: /Compare vendors\. Compare,/ });
    expect(compareThread).toBeInTheDocument();

    await user.click(compareThread);
    expect(onSelectThread).toHaveBeenCalledTimes(1);
    expect(onSelectThread.mock.calls[0]?.[0].sessionId).toBe("compare-session");
  });

  it("starts a new chat without changing sidebar navigation behavior", async () => {
    const user = userEvent.setup();
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
      mode: "compare",
    });

    render(<Sidebar onSelectThread={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "New chat" }));

    expect(useChatStore.getState().sessionId).toBeNull();
    expect(useChatStore.getState().pendingNewSession).toBe(true);
    expect(useChatStore.getState().mode).toBe("compare");
    expect(screen.getByText("Quarterly planning")).toBeInTheDocument();
  });

  it("collapses and expands the desktop sidebar while keeping icon actions usable", async () => {
    const user = userEvent.setup();
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
      mode: "single",
    });

    render(<Sidebar onSelectThread={vi.fn()} />);

    const sidebar = screen.getByLabelText("Primary navigation");
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(screen.getByRole("textbox", { name: "Search history" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));

    expect(sidebar).toHaveAttribute("data-collapsed", "true");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("textbox", { name: "Search history" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(useChatStore.getState().mode).toBe("compare");

    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(useChatStore.getState().sessionId).toBeNull();

    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));

    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getByRole("textbox", { name: "Search history" })).toBeInTheDocument();
  });

  it("clears the active persisted thread after confirmation", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      statusText: "No Content",
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
    });

    render(<Sidebar onSelectThread={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Clear" }));

    await waitFor(() =>
      expect(useChatStore.getState().history.map((entry) => entry.id)).toEqual([3, 4]),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/history?session_id=ask-session",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    );
    expect(useChatStore.getState().sessionId).toBeNull();
    expect(screen.queryByText("Quarterly planning")).toBeNull();
    expect(screen.getByText("Compare vendors")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Primary navigation")).getByText("Clear")).toBeInTheDocument();
  });

  it("marks Usage active and routes Ask or Compare back to chat", async () => {
    const user = userEvent.setup();
    const onNavigateChat = vi.fn<(mode: "single" | "compare") => void>();
    const onNavigateUsage = vi.fn();
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
      mode: "single",
    });

    render(
      <Sidebar
        onSelectThread={vi.fn()}
        activeView="usage"
        onNavigateChat={onNavigateChat}
        onNavigateUsage={onNavigateUsage}
      />,
    );

    expect(screen.getByRole("button", { name: "Usage" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "Ask" })).not.toHaveAttribute(
      "aria-current",
    );

    await user.click(screen.getByRole("button", { name: "Compare" }));

    expect(useChatStore.getState().mode).toBe("compare");
    expect(onNavigateChat).toHaveBeenCalledWith("compare");

    await user.click(screen.getByRole("button", { name: "Usage" }));
    expect(onNavigateUsage).toHaveBeenCalledTimes(1);
  });

  it("keeps the signed-in session footer as status instead of a sign-out action", async () => {
    const user = userEvent.setup();
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
    });

    render(
      <Sidebar
        onSelectThread={vi.fn()}
        loggedIn
        whoAmI={whoAmI()}
      />,
    );

    expect(screen.queryByRole("button", { name: /Sign out/i })).not.toBeInTheDocument();
    expect(screen.getByText("Session active").closest("button")).toBeNull();
    await user.click(screen.getByText("Session active"));
  });

  it("keeps the sidebar footer sign-in action for signed-out users", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn();

    render(<Sidebar onSelectThread={vi.fn()} loggedIn={false} onLogin={onLogin} />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(onLogin).toHaveBeenCalledTimes(1);
  });

  it("deletes every persisted entry in a history thread", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      statusText: "No Content",
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    useChatStore.setState({
      history: historyEntries(),
      sessionId: "ask-session",
      pendingNewSession: false,
    });

    const onSelectThread = vi.fn();

    render(<Sidebar onSelectThread={onSelectThread} />);
    const activeThread = screen.getByRole("button", { name: /Quarterly planning\. Ask,/ });
    const activeRow = activeThread.closest("li");
    expect(activeRow).not.toBeNull();

    await user.click(within(activeRow!).getByRole("button", { name: "Delete chat" }));

    expect(onSelectThread).not.toHaveBeenCalled();
    expect(within(activeRow!).getByText("Delete?")).toBeInTheDocument();
    await user.click(within(activeRow!).getByRole("button", { name: "Confirm delete chat" }));

    await waitFor(() =>
      expect(useChatStore.getState().history.map((entry) => entry.id)).toEqual([3, 4]),
    );
    const deletedPaths = fetchMock.mock.calls.map((call) => call[0]);
    expect(deletedPaths).toContain("/v1/history/1");
    expect(deletedPaths).toContain("/v1/history/2");
    expect(deletedPaths).not.toContain("/v1/history/3");
    expect(deletedPaths).not.toContain("/v1/history/4");
    expect(useChatStore.getState().sessionId).toBeNull();
    expect(screen.queryByText("Quarterly planning")).toBeNull();
    expect(screen.getByText("Compare vendors")).toBeInTheDocument();
  });
});

function historyEntries(): HistoryEntry[] {
  return [
    historyEntry({
      id: 1,
      sessionId: "ask-session",
      prompt: "Quarterly planning",
      response: "Planning response",
      mode: "single",
      provider: "openai",
      model: "gpt-5.1",
      timestamp: "2026-06-10T10:00:00Z",
    }),
    historyEntry({
      id: 2,
      sessionId: "ask-session",
      prompt: "Add milestones",
      response: "Milestone response",
      mode: "single",
      provider: "openai",
      model: "gpt-5.1",
      timestamp: "2026-06-10T10:01:00Z",
    }),
    historyEntry({
      id: 3,
      sessionId: "compare-session",
      prompt: "Compare vendors",
      response: "OpenAI comparison",
      mode: "compare",
      provider: "openai",
      model: "gpt-5.1",
      requestGroupId: "compare-group",
      timestamp: "2026-06-10T11:00:00Z",
    }),
    historyEntry({
      id: 4,
      sessionId: "compare-session",
      prompt: "Compare vendors",
      response: "Claude comparison",
      mode: "compare",
      provider: "claude",
      model: "claude-sonnet-4-5",
      requestGroupId: "compare-group",
      timestamp: "2026-06-10T11:00:00Z",
    }),
  ];
}

function historyEntry({
  id,
  sessionId,
  prompt,
  response,
  mode,
  provider,
  model,
  timestamp,
  requestGroupId,
}: {
  id: number;
  sessionId: string;
  prompt: string;
  response: string;
  mode: string;
  provider: string;
  model: string;
  timestamp: string;
  requestGroupId?: string;
}): HistoryEntry {
  return {
    id,
    session_id: sessionId,
    request_group_id: requestGroupId,
    timestamp,
    mode,
    prompt,
    provider,
    model,
    response,
    latency_ms: 300,
    tokens: 40,
    cost: 0.001,
    web_source_items: [],
  };
}

function whoAmI() {
  return {
    api_key_id: "test-key",
    user_id: "signed-in-user",
    plan_tier: "Pro",
    storage_policy: "full",
    redact_pii: false,
    baseline: {
      provider: "openai",
      model: "gpt-5.1",
      source: "test",
    },
    rate_limits: {
      requests_per_minute: 60,
      daily_cap_scope: "user",
    },
    breakers: {
      failure_threshold: 5,
      window_seconds: 60,
      cooldown_seconds: 120,
      scope: "provider_model",
    },
  };
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}
