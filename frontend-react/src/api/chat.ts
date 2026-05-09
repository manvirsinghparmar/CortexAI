import { streamPost } from "./client";
import type { ChatRequest, ChatResponse, StreamChunk } from "../types";

/**
 * Streams a chat response from /v1/chat/stream.
 *
 * Backend sends NDJSON with types: start | line | response_done | done | error.
 * We normalise these into StreamChunk (delta | metadata | done | error).
 */
export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamChunk> {
  const lines = streamPost("/v1/chat/stream", request);

  for await (const line of lines) {
    if (signal?.aborted) break;
    const trimmed = line.trim();
    if (!trimmed || trimmed === "data: [DONE]") continue;

    const raw = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;

    let event: Record<string, unknown>;
    try {
      event = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      yield { type: "delta", text: raw };
      continue;
    }

    switch (event.type) {
      case "line":
        yield { type: "delta", text: String(event.text ?? "") };
        break;
      case "response_done":
        yield { type: "metadata", metadata: event.response as Partial<ChatResponse> };
        break;
      case "done":
        yield { type: "done" };
        break;
      case "error":
        yield { type: "error", error: String(event.message ?? "Unknown error") };
        break;
      // "start" — ignore, no UI action needed
    }
  }
}

/**
 * Sends a non-streaming chat request. Used as a fallback when SSE is unavailable.
 */
export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const res = await fetch("/v1/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(String((err as { detail?: string }).detail ?? res.statusText));
  }
  return res.json() as Promise<ChatResponse>;
}
