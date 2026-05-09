import { post, streamPost } from "./client";
import type { CompareRequest, CompareResponse, ChatResponse } from "../types";

export async function sendCompare(request: CompareRequest): Promise<CompareResponse> {
  return post<CompareResponse>("/v1/compare", request);
}

export type CompareStreamEvent =
  | { type: "response_start"; index: number; provider: string; model: string }
  | { type: "line"; index: number; text: string }
  | { type: "response_done"; index: number; response: ChatResponse }
  | { type: "done"; session_id: string | null; responses: ChatResponse[] }
  | { type: "error"; message: string };

export async function* streamCompare(
  request: CompareRequest,
  signal?: AbortSignal,
): AsyncGenerator<CompareStreamEvent> {
  const lines = streamPost("/v1/compare/stream", request);

  for await (const line of lines) {
    if (signal?.aborted) break;
    const trimmed = line.trim();
    if (!trimmed) continue;

    const raw = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      continue;
    }

    switch (event.type) {
      case "response_start":
        yield {
          type: "response_start",
          index: Number(event.index),
          provider: String(event.provider ?? ""),
          model: String(event.model ?? ""),
        };
        break;
      case "line":
        yield { type: "line", index: Number(event.index), text: String(event.text ?? "") };
        break;
      case "response_done":
        yield {
          type: "response_done",
          index: Number(event.index),
          response: event.response as ChatResponse,
        };
        break;
      case "done":
        yield {
          type: "done",
          session_id: (event.session_id as string | null) ?? null,
          responses: (event.responses as ChatResponse[]) ?? [],
        };
        break;
      case "error":
        yield { type: "error", message: String(event.message ?? "Compare stream error") };
        break;
      // "start" — ignore
    }
  }
}
