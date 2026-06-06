import { act, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ResultsSection } from "../components/results/ResultsSection";
import { useChatStore } from "../store/chatStore";
import type { ChatResponse } from "../types";

describe("ResultsSection", () => {
  afterEach(() => {
    act(() => {
      useChatStore.setState({
        mode: "compare",
        responses: [],
        streaming: false,
        streamingText: "",
      });
    });
  });

  it("marks the lowest latency compare response as fastest", () => {
    act(() => {
      useChatStore.setState({
        mode: "compare",
        responses: [
          response("openai-1", "openai", "gpt-4o", 420),
          response("gemini-1", "gemini", "gemini-2.5-flash", 580),
        ],
        streaming: false,
        streamingText: "",
      });
    });

    render(<ResultsSection />);

    const gptCard = screen.getByRole("heading", { name: "gpt-4o" }).closest("article");
    const geminiCard = screen
      .getByRole("heading", { name: "gemini-2.5-flash" })
      .closest("article");

    expect(gptCard).not.toBeNull();
    expect(geminiCard).not.toBeNull();
    expect(within(gptCard!).getByText("FASTEST")).toBeDefined();
    expect(within(geminiCard!).queryByText("FASTEST")).toBeNull();
  });
});

function response(
  requestId: string,
  provider: string,
  model: string,
  latencyMs: number,
): ChatResponse {
  return {
    request_id: requestId,
    text: "Done",
    provider,
    model,
    latency_ms: latencyMs,
    token_usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 },
    estimated_cost: 0,
    cost_currency: "USD",
    web_source_items: [],
    timestamp: new Date().toISOString(),
  };
}
