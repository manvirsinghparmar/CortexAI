import { streamPost } from "./client";
import type { ChatRequest, ChatResponse, StreamChunk } from "../types";

/**
 * Streams a chat response from /v1/chat.
 *
 * The backend sends newline-delimited JSON where each line is a StreamChunk.
 * Falls back gracefully if the server returns plain text lines.
 */
export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamChunk> {
  const lines = streamPost("/v1/chat", request);

  for await (const line of lines) {
    if (signal?.aborted) break;
    const trimmed = line.trim();
    if (!trimmed || trimmed === "data: [DONE]") continue;

    // Handle SSE "data: {...}" envelope if present
    const raw = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;

    try {
      const chunk = JSON.parse(raw) as StreamChunk;
      yield chunk;
    } catch {
      // Plain text delta line from the server
      yield { type: "delta", text: raw };
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
