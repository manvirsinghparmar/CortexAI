import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamPost } from "../api/client";
import { streamChat } from "../api/chat";

vi.mock("../api/client", () => ({
  post: vi.fn(),
  streamPost: vi.fn(),
}));

describe("streamChat", () => {
  beforeEach(() => {
    vi.mocked(streamPost).mockReset();
  });

  it("preserves the routed provider and model from the start event", async () => {
    vi.mocked(streamPost).mockReturnValue(
      streamLines([
        JSON.stringify({
          type: "start",
          provider: "claude",
          model: "claude-sonnet-4-5",
          session_id: "session-1",
        }),
      ]),
    );

    const chunks = [];
    for await (const chunk of streamChat({ prompt: "Explain this" })) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual([
      {
        type: "start",
        provider: "claude",
        model: "claude-sonnet-4-5",
        session_id: "session-1",
      },
    ]);
  });
});

async function* streamLines(lines: string[]): AsyncGenerator<string> {
  for (const line of lines) yield line;
}
