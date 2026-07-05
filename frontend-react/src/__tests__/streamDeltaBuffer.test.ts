import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makePlaceholderResponse, useChatStore } from "../store/chatStore";
import { StreamDeltaBuffer } from "../streaming/streamDeltaBuffer";

describe("StreamDeltaBuffer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useChatStore.getState().startNewChat();
  });

  afterEach(() => {
    vi.useRealTimers();
    useChatStore.getState().startNewChat();
  });

  it("batches deltas until the flush interval", () => {
    const turnId = useChatStore.getState().beginTurn({
      mode: "single",
      prompt: "hello",
      submittedPrompt: "hello",
      attachments: [],
      responses: [makePlaceholderResponse(0, "openai", "gpt-test")],
    });
    const buffer = new StreamDeltaBuffer(turnId);

    buffer.append(0, "Hel");
    buffer.append(0, "lo");
    vi.advanceTimersByTime(119);

    expect(useChatStore.getState().turns[0]?.responses[0]?.text).toBe("");

    vi.advanceTimersByTime(1);

    expect(useChatStore.getState().turns[0]?.responses[0]?.text).toBe("Hello");
  });

  it("dispose clears pending text and timers after cancellation", () => {
    const turnId = useChatStore.getState().beginTurn({
      mode: "single",
      prompt: "hello",
      submittedPrompt: "hello",
      attachments: [],
      responses: [makePlaceholderResponse(0, "openai", "gpt-test")],
    });
    const buffer = new StreamDeltaBuffer(turnId);

    buffer.append(0, "stale text");
    useChatStore.getState().setTurnStatus(turnId, "cancelled");
    buffer.dispose();
    vi.runAllTimers();

    expect(useChatStore.getState().turns[0]?.responses[0]?.text).toBe("");
  });
});
