import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResultsSection } from "../components/results/ResultsSection";
import { useChatStore } from "../store/chatStore";
import type { ChatResponse, ChatTurn } from "../types";

const originalScrollTo = HTMLElement.prototype.scrollTo;

describe("ResultsSection layout states", () => {
  afterEach(() => {
    cleanup();
    useChatStore.getState().startNewChat();
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: originalScrollTo,
    });
  });

  it("keeps one Compare turn in the full-height transcript layout", () => {
    setTurns([compareTurn("compare-1", "First comparison")]);

    render(<ResultsSection />);

    const transcriptGrid = screen.getByLabelText("Chat transcript").firstElementChild;
    const comparison = screen.getByLabelText("Model comparison");
    expect(transcriptGrid?.className).toContain("oneTurnGrid");
    expect(comparison.className).not.toContain("constrainedCompareTurn");
  });

  it("keeps every Compare turn in the tall panel grid for multi-turn transcripts", () => {
    setTurns([
      compareTurn("compare-1", "First comparison"),
      compareTurn("compare-2", "Second comparison"),
    ]);

    render(<ResultsSection />);

    const transcriptGrid = screen.getByLabelText("Chat transcript").firstElementChild;
    expect(transcriptGrid?.className).toContain("multiTurnGrid");
    for (const comparison of screen.getAllByLabelText("Model comparison")) {
      expect(comparison.className).toContain("compareTurn");
    }
  });

  it("leaves Ask turns content-sized in a mixed multi-turn transcript", () => {
    setTurns([
      askTurn("ask-1", "Ask question"),
      compareTurn("compare-1", "Compare follow-up"),
    ]);

    render(<ResultsSection />);

    const askMessage = document.querySelector("#chat-msg-0");
    const askArticle = askMessage?.closest("article");
    const comparison = screen.getByLabelText("Model comparison");
    expect(askArticle?.className).not.toContain("constrainedCompareTurn");
    expect(comparison.className).toContain("compareTurn");
  });

  it("renders Compare prompts with the same user bubble as Ask prompts", () => {
    setTurns([
      askTurn("ask-1", "Ask question"),
      compareTurn("compare-1", "Compare question"),
    ]);

    render(<ResultsSection />);

    const askPrompt = screen.getByText("Ask question").closest("div");
    const comparePrompt = screen.getByText("Compare question").closest("div");
    expect(askPrompt?.className).toContain("userBubble");
    expect(comparePrompt?.className).toBe(askPrompt?.className);
    expect(screen.getAllByText("You")).toHaveLength(2);
    expect(screen.queryByText("Prompt")).not.toBeInTheDocument();
  });

  it("keeps Compare loading states independent per model", () => {
    const turn = compareTurn("compare-streaming", "Compare streaming");
    turn.status = "streaming";
    turn.responses = [
      { ...turn.responses[0]!, text: "GPT has started responding." },
      { ...turn.responses[1]!, text: "" },
    ];
    setTurns([turn]);

    render(<ResultsSection />);

    expect(screen.getByText("GPT has started responding.")).toBeInTheDocument();
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent("Generating response\u2026");
  });

  it("renders the Compare run summary with fastest and cheapest metric tags", () => {
    const turn = compareTurn("compare-metrics", "Compare metrics");
    turn.responses = [
      response("compare-metrics-openai", "openai", "gpt-5.1", {
        latency_ms: 640,
        estimated_cost: 0.0018,
      }),
      response("compare-metrics-claude", "claude", "claude-sonnet-4-5", {
        latency_ms: 320,
        estimated_cost: 0.0024,
      }),
      response("compare-metrics-deepseek", "deepseek", "deepseek-chat", {
        latency_ms: 510,
        estimated_cost: 0.0005,
      }),
    ];
    turn.compareSummary = {
      request_group_id: "compare-metrics-group",
      responses: turn.responses,
      success_count: 3,
      error_count: 0,
      total_tokens: 300,
      total_cost: 0.0047,
      timestamp: "2026-06-09T00:00:00.000Z",
    };
    setTurns([turn]);

    render(<ResultsSection />);

    expect(screen.getByText("3 succeeded")).toBeInTheDocument();
    expect(screen.getByText("0 errors")).toBeInTheDocument();
    expect(screen.getByText("300 tok")).toBeInTheDocument();
    expect(screen.getByText("$0.00470")).toBeInTheDocument();
    const fastestLabel = screen.getByText(/Fastest/);
    const cheapestLabel = screen.getByText(/Cheapest/);
    expect(fastestLabel).toHaveClass("winner-label");
    expect(fastestLabel.parentElement).toHaveTextContent("0.3s");
    expect(cheapestLabel).toHaveClass("winner-label");
    expect(cheapestLabel.parentElement).toHaveTextContent("$0.0005");
  });

  it("switches the active mobile Compare response from the model tabs", async () => {
    const user = userEvent.setup();
    setTurns([compareTurn("compare-switcher", "Compare responses")]);

    render(<ResultsSection />);

    const gptTab = screen.getByRole("tab", { name: "GPT-5.1" });
    const claudeTab = screen.getByRole("tab", { name: "Claude Sonnet" });
    const gptPanel = screen.getByRole("tabpanel", { name: "GPT-5.1" });
    const claudePanel = screen.getByRole("tabpanel", { name: "Claude Sonnet" });

    expect(gptTab).toHaveAttribute("aria-selected", "true");
    expect(claudeTab).toHaveAttribute("aria-selected", "false");
    expect(gptPanel.className).toContain("mobileResponsePanelActive");
    expect(claudePanel.className).not.toContain("mobileResponsePanelActive");

    await user.click(claudeTab);

    expect(gptTab).toHaveAttribute("aria-selected", "false");
    expect(claudeTab).toHaveAttribute("aria-selected", "true");
    expect(gptPanel.className).not.toContain("mobileResponsePanelActive");
    expect(claudePanel.className).toContain("mobileResponsePanelActive");
  });

  it("uses the submitted turn flags for source-enabled Ask loading copy", () => {
    const turn = askTurn("ask-streaming", "Research this");
    turn.status = "streaming";
    turn.researchEnabled = true;
    turn.responses = [{ ...turn.responses[0]!, text: "" }];
    setTurns([turn]);

    render(<ResultsSection />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking sources and preparing an answer\u2026",
    );
  });

  it.each([
    ["Ask", askTurn("ask-1", "First Ask"), askTurn("ask-2", "Latest Ask")],
    [
      "Compare",
      compareTurn("compare-1", "First comparison"),
      compareTurn("compare-2", "Latest comparison"),
    ],
  ])("reveals every newly submitted %s turn", async (_, first, latest) => {
    const scrollTo = mockTranscriptScroll();
    setTurns([first]);
    render(<ResultsSection />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    await settleScrollFollowUp();
    scrollTo.mockClear();

    act(() => setTurns([first, latest]));

    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    expect(document.querySelector(`[data-turn-id="${latest.id}"]`)).toBeInTheDocument();
  });

  it("does not keep scrolling when the active response grows", async () => {
    const scrollTo = mockTranscriptScroll();
    const first = compareTurn("compare-1", "First comparison");
    const latest = compareTurn("compare-2", "Latest comparison");
    setTurns([first]);
    render(<ResultsSection />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    await settleScrollFollowUp();
    scrollTo.mockClear();

    act(() => setTurns([first, latest]));
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    await settleScrollFollowUp();
    scrollTo.mockClear();

    act(() => {
      useChatStore
        .getState()
        .appendTurnResponseText(latest.id, 0, " Additional streamed response text.");
    });
    await settleScrollFollowUp();

    expect(scrollTo).not.toHaveBeenCalled();
  });

  it("reveals a newly submitted turn even when the user was viewing an older turn", async () => {
    const scrollTo = mockTranscriptScroll();
    const first = askTurn("ask-1", "First Ask");
    const latest = askTurn("ask-2", "Latest Ask");
    setTurns([first]);
    render(<ResultsSection />);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    await settleScrollFollowUp();
    scrollTo.mockClear();

    act(() => setTurns([first, latest]));

    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
    expect(document.querySelector(`[data-turn-id="${latest.id}"]`)).toBeInTheDocument();
  });
});

function setTurns(turns: ChatTurn[]) {
  const latestTurn = turns[turns.length - 1];
  useChatStore.setState({
    turns,
    activeTurnId: latestTurn?.id ?? null,
    responses: latestTurn?.responses ?? [],
    streaming: false,
  });
}

function compareTurn(id: string, prompt: string): ChatTurn {
  const responses = [
    response(`${id}-openai`, "openai", "gpt-5.1"),
    response(`${id}-claude`, "claude", "claude-sonnet-4-5"),
  ];
  return {
    id,
    mode: "compare",
    prompt,
    submittedPrompt: prompt,
    attachments: [],
    responses,
    status: "complete",
    createdAt: "2026-06-09T00:00:00.000Z",
    requestGroupId: `${id}-group`,
    compareSummary: {
      request_group_id: `${id}-group`,
      responses,
      success_count: 2,
      error_count: 0,
      total_tokens: 120,
      total_cost: 0.002,
      timestamp: "2026-06-09T00:00:00.000Z",
    },
  };
}

function askTurn(id: string, prompt: string): ChatTurn {
  return {
    id,
    mode: "single",
    prompt,
    submittedPrompt: prompt,
    attachments: [],
    responses: [response(`${id}-response`, "openai", "gpt-5.1")],
    status: "complete",
    createdAt: "2026-06-09T00:00:00.000Z",
  };
}

function response(
  requestId: string,
  provider: string,
  model: string,
  overrides: Partial<ChatResponse> = {},
): ChatResponse {
  return {
    request_id: requestId,
    text: "A long response remains inside its own scrollable card body.",
    provider,
    model,
    latency_ms: 320,
    token_usage: {
      prompt_tokens: 20,
      completion_tokens: 40,
      total_tokens: 60,
    },
    estimated_cost: 0.001,
    cost_currency: "USD",
    web_source_items: [],
    timestamp: "2026-06-09T00:00:00.000Z",
    ...overrides,
  };
}

function mockTranscriptScroll() {
  const scrollTo = vi.fn();
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: scrollTo,
  });
  return scrollTo;
}

async function settleScrollFollowUp() {
  await act(async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  });
}
