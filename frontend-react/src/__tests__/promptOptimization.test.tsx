import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FeatureChips } from "../components/composer/FeatureChips";
import { ResultsSection } from "../components/results/ResultsSection";
import { useChat } from "../hooks/useChat";
import { buildConversationHistory } from "../hooks/useChat";
import {
  buildOptimizeRequest,
  OPTIMIZATION_ORIGINAL_NOTE,
  resolveOptimizationFailure,
  resolveOptimizationResponse,
} from "../optimization/promptOptimization";
import { useChatStore } from "../store/chatStore";
import type {
  ChatTurn,
  ConversationHistoryItem,
  FileUploadResponse,
  OptimizeResponse,
} from "../types";

describe("prompt optimization", () => {
  beforeEach(() => {
    useChatStore.setState({
      mode: "single",
      smartMode: true,
      researchMode: false,
      compareResearchMode: true,
      optimizeMode: false,
      selectedModelKey: "openai:gpt-5.1",
      compareModelKeys: [
        "openai:gpt-5.1",
        "claude:claude-sonnet-4-5",
        "",
      ],
      prompt: "",
      attachments: [],
      turns: [],
      activeTurnId: null,
      responses: [],
      streaming: false,
      streamingText: "",
      error: null,
      history: [],
      historySearch: "",
      sessionId: null,
      pendingNewSession: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends no context for a first prompt even when it contains a reference word", () => {
    expect(
      buildOptimizeRequest({
        prompt: "Make this clearer",
        conversationHistory: [],
        context: { new_session: true },
        attachments: [],
      }),
    ).toEqual({ prompt: "Make this clearer" });
  });

  it("bounds context for a likely follow-up and preserves the active session", () => {
    const conversationHistory: ConversationHistoryItem[] = Array.from(
      { length: 12 },
      (_, index) => ({
        role: index % 2 === 0 ? "user" : "assistant",
        content: `${index} ${"detail ".repeat(100)}`,
      }),
    );

    const request = buildOptimizeRequest({
      prompt: "I was talking about mining the asteroids",
      conversationHistory,
      context: { session_id: "session-1", new_session: false },
      attachments: [],
    });

    expect(request.context?.session_id).toBe("session-1");
    expect(request.context?.conversation_history).toHaveLength(10);
    expect(
      request.context?.conversation_history?.every((message) => message.content.length <= 500),
    ).toBe(true);
    expect(request.context_hint?.length).toBeLessThanOrEqual(2000);
  });

  it("does not duplicate attachment context into the optimization request", () => {
    expect(
      buildOptimizeRequest({
        prompt: "Summarize that",
        conversationHistory: [{ role: "assistant", content: "Previous answer" }],
        context: { session_id: "session-1" },
        attachments: [attachment()],
      }),
    ).toEqual({ prompt: "Summarize that" });
  });

  it("uses the exact optimized prompt as the visible and submitted prompt", () => {
    const response: OptimizeResponse = {
      original_prompt: "rough prompt",
      optimized_prompt: "Clear, specific prompt",
      was_optimized: true,
      server_optimization_enabled: true,
      optimization_status: "optimized",
    };

    const resolved = resolveOptimizationResponse(response, "rough prompt");

    expect(resolved.finalPrompt).toBe("Clear, specific prompt");
    expect(resolved.optimization.displayPrompt).toBe("Clear, specific prompt");
    expect(resolved.optimization.note).toBeUndefined();
  });

  it("keeps the original prompt with a visible reassurance on fallback", () => {
    const resolved = resolveOptimizationFailure("Already clear");

    expect(resolved.finalPrompt).toBe("Already clear");
    expect(resolved.optimization.status).toBe("kept_original");
    expect(resolved.optimization.note).toBe(OPTIMIZATION_ORIGINAL_NOTE);
  });

  it("renders optimization progress without a response placeholder", () => {
    useChatStore.setState({
      turns: [
        turn({
          status: "optimizing",
          optimization: {
            status: "pending",
            originalPrompt: "rough prompt",
            displayPrompt: "rough prompt",
          },
        }),
      ],
    });

    render(<ResultsSection />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Refining your prompt for better results",
    );
    expect(screen.queryByText("Waiting for response...")).not.toBeInTheDocument();
  });

  it("renders the fallback note beneath the original prompt", () => {
    useChatStore.setState({
      turns: [
        turn({
          prompt: "Already clear",
          submittedPrompt: "Already clear",
          optimization: resolveOptimizationFailure("Already clear").optimization,
        }),
      ],
    });

    render(<ResultsSection />);

    expect(screen.getByText("Already clear")).toBeInTheDocument();
    expect(screen.getByText(OPTIMIZATION_ORIGINAL_NOTE)).toHaveClass(
      "optimization-result-note",
    );
  });

  it("keeps Improve available in Compare mode", () => {
    render(
      <FeatureChips
        compareMode
        smartMode={false}
        researchMode={true}
        optimizeMode={true}
        onSmartToggle={vi.fn()}
        onResearchToggle={vi.fn()}
        onOptimizeToggle={vi.fn()}
      />,
    );

    expect(screen.getByRole("switch", { name: "Prompt optimization" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("omits optimizing and cancelled turns from future conversation context", () => {
    const completed = turn({
      id: "complete",
      prompt: "Completed prompt",
      submittedPrompt: "Completed prompt",
    });
    const optimizing = turn({
      id: "optimizing",
      prompt: "Pending prompt",
      submittedPrompt: "Pending prompt",
      status: "optimizing",
    });
    const cancelled = turn({
      id: "cancelled",
      prompt: "Cancelled prompt",
      submittedPrompt: "Cancelled prompt",
      status: "cancelled",
    });

    expect(buildConversationHistory([completed, optimizing, cancelled])).toEqual([
      { role: "user", content: "Completed prompt" },
    ]);
  });

  it("aborts optimization without starting a chat request", async () => {
    const fetchMock = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          const rejectAbort = () =>
            reject(new DOMException("The operation was aborted.", "AbortError"));
          if (init?.signal?.aborted) {
            rejectAbort();
            return;
          }
          init?.signal?.addEventListener("abort", rejectAbort, { once: true });
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    useChatStore.setState({
      optimizeMode: true,
      prompt: "Cancel this optimization",
    });

    render(
      <>
        <ChatActions />
        <ResultsSection />
      </>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(
      await screen.findByText("Refining your prompt for better results"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(screen.getByText("Optimization stopped.")).toBeInTheDocument();
    });
    expect(useChatStore.getState().streaming).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/v1/optimize");
  });
});

function ChatActions() {
  const { submit, cancel } = useChat();
  return (
    <>
      <button type="button" onClick={() => void submit()}>
        Submit
      </button>
      <button type="button" onClick={cancel}>
        Cancel
      </button>
    </>
  );
}

function turn(overrides: Partial<ChatTurn> = {}): ChatTurn {
  return {
    id: "turn-1",
    mode: "single",
    prompt: "Prompt",
    submittedPrompt: "Prompt",
    attachments: [],
    responses: [],
    status: "complete",
    createdAt: "2026-06-07T00:00:00.000Z",
    ...overrides,
  };
}

function attachment(): FileUploadResponse {
  return {
    file_id: "file-1",
    original_filename: "report.pdf",
    mime_type: "application/pdf",
    size_bytes: 100,
    status: "ready",
    ingestion_meta: {},
    created_at: "2026-06-07T00:00:00.000Z",
    deduplicated: false,
  };
}
