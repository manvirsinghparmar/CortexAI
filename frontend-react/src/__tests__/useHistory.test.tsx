import { useEffect } from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useHistory } from "../hooks/useHistory";
import { ACTIVE_SESSION_STORAGE_KEY, persistActiveSessionId } from "../session/activeSession";
import { useChatStore } from "../store/chatStore";
import type { HistoryEntry } from "../types";

describe("useHistory", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
    resetStore();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    resetStore();
  });

  it("restores the persisted active transcript after startup history load", async () => {
    persistActiveSessionId("ask-session");
    vi.stubGlobal("fetch", fetchHistoryMock(historyEntries()));

    render(<HistoryLoader restoreActiveTranscript />);

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.sessionId).toBe("ask-session");
      expect(state.pendingNewSession).toBe(false);
      expect(state.turns).toHaveLength(2);
      expect(state.turns[0]?.prompt).toBe("Quarterly planning");
      expect(state.turns[1]?.prompt).toBe("Add milestones");
    });

    expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBe("ask-session");
  });

  it("checks the persisted session directly when it is outside the initial history window", async () => {
    persistActiveSessionId("old-session");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const entries = url.includes("session_id=old-session")
        ? [
            historyEntry({
              id: 99,
              sessionId: "old-session",
              prompt: "Older selected thread",
              response: "Older response",
              timestamp: "2026-06-01T10:00:00Z",
            }),
          ]
        : historyEntries();
      return jsonResponse(entries);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HistoryLoader restoreActiveTranscript />);

    await waitFor(() => {
      const state = useChatStore.getState();
      expect(state.sessionId).toBe("old-session");
      expect(state.turns[0]?.prompt).toBe("Older selected thread");
      expect(state.history.some((entry) => entry.session_id === "old-session")).toBe(true);
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/v1/history?limit=500&session_id=old-session",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
  });

  it("clears stale persisted active session ids that do not belong to the current user", async () => {
    useChatStore.getState().setSessionId("missing-session");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      return jsonResponse(url.includes("session_id=missing-session") ? [] : historyEntries());
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HistoryLoader restoreActiveTranscript />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/v1/history?limit=500&session_id=missing-session",
        expect.any(Object),
      );
    });

    expect(useChatStore.getState().sessionId).toBeNull();
    expect(useChatStore.getState().turns).toEqual([]);
    expect(window.localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY)).toBeNull();
  });
});

function HistoryLoader({ restoreActiveTranscript }: { restoreActiveTranscript: boolean }) {
  const { load } = useHistory();

  useEffect(() => {
    void load({ restoreActiveTranscript });
  }, [load, restoreActiveTranscript]);

  return null;
}

function fetchHistoryMock(entries: HistoryEntry[]) {
  return vi.fn(async () => jsonResponse(entries));
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function historyEntries(): HistoryEntry[] {
  return [
    historyEntry({
      id: 1,
      sessionId: "ask-session",
      prompt: "Quarterly planning",
      response: "Planning response",
      timestamp: "2026-06-10T10:00:00Z",
    }),
    historyEntry({
      id: 2,
      sessionId: "ask-session",
      prompt: "Add milestones",
      response: "Milestone response",
      timestamp: "2026-06-10T10:01:00Z",
    }),
  ];
}

function historyEntry({
  id,
  sessionId,
  prompt,
  response,
  timestamp,
}: {
  id: number;
  sessionId: string;
  prompt: string;
  response: string;
  timestamp: string;
}): HistoryEntry {
  return {
    id,
    session_id: sessionId,
    request_group_id: undefined,
    timestamp,
    mode: "single",
    prompt,
    provider: "openai",
    model: "gpt-5.1",
    response,
    latency_ms: 300,
    tokens: 40,
    cost: 0.001,
    web_source_items: [],
  };
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}
