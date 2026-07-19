import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientError } from "../api/client";
import { useChat } from "../hooks/useChat";
import { useChatStore } from "../store/chatStore";
import type { FileUploadResponse } from "../types";

const apiMocks = vi.hoisted(() => ({
  streamChat: vi.fn(),
  streamCompare: vi.fn(),
  optimizePrompt: vi.fn(),
  fetchHistory: vi.fn().mockResolvedValue([]),
}));

vi.mock("../api/chat", () => ({ streamChat: apiMocks.streamChat }));
vi.mock("../api/compare", () => ({ streamCompare: apiMocks.streamCompare }));
vi.mock("../api/optimize", () => ({ optimizePrompt: apiMocks.optimizePrompt }));
vi.mock("../api/history", () => ({ fetchHistory: apiMocks.fetchHistory }));

describe("subscription denial draft preservation", () => {
  beforeEach(() => {
    useChatStore.getState().startNewChat();
    useChatStore.setState({
      mode: "single",
      smartMode: false,
      researchMode: false,
      optimizeMode: false,
      selectedModelKey: "openai:gpt-5.1",
      prompt: "Keep my exact draft",
      attachments: [attachment()],
      subscriptionError: null,
      error: null,
    });
    apiMocks.streamChat.mockImplementation(() => deniedStream());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the prompt and attachments and removes the optimistic turn", async () => {
    const { result } = renderHook(() => useChat());

    await act(async () => {
      await result.current.submit();
    });

    const state = useChatStore.getState();
    expect(state.prompt).toBe("Keep my exact draft");
    expect(state.attachments).toEqual([attachment()]);
    expect(state.turns).toEqual([]);
    expect(state.responses).toEqual([]);
    expect(state.streaming).toBe(false);
    expect(state.error).toBeNull();
    expect(state.subscriptionError?.code).toBe("monthly_allowance_exhausted");
    expect(state.subscriptionError?.details.meter).toBe("model_responses");
  });
});

async function* deniedStream() {
  yield* [];
  throw new ApiClientError(429, "The monthly model response allowance has been exhausted.", {
    detail: {
      code: "monthly_allowance_exhausted",
      message: "The monthly model response allowance has been exhausted.",
      meter: "model_responses",
      current_plan: "free",
      recommended_plan: "plus",
      remaining: 0,
      reset_at: "2026-08-19T00:00:00Z",
    },
  });
}

function attachment(): FileUploadResponse {
  return {
    file_id: "file-draft",
    original_filename: "draft.pdf",
    mime_type: "application/pdf",
    size_bytes: 2048,
    status: "ready",
    ingestion_meta: {},
    created_at: "2026-07-19T00:00:00Z",
    deduplicated: false,
  };
}
