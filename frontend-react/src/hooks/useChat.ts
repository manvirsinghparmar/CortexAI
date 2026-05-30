import { useCallback, useRef } from "react";
import { streamChat } from "../api/chat";
import { sendCompare } from "../api/compare";
import { optimizePrompt } from "../api/optimize";
import { useChatStore } from "../store/chatStore";
import { parseModelKey } from "./useSmartRouting";
import type { ChatRequest, CompareRequest, ChatResponse } from "../types";

export function useChat() {
  const store = useChatStore();
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(async () => {
    const {
      mode,
      prompt,
      smartMode,
      researchMode,
      optimizeMode,
      selectedModelKey,
      compareModelKeys,
      attachments,
      sessionId,
      setStreaming,
      setStreamingText,
      appendStreamingText,
      setResponses,
      setError,
      setSessionId,
    } = store;

    if (!prompt.trim() && attachments.length === 0) return;

    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setError(null);
    setStreaming(true);
    setStreamingText("");

    let finalPrompt = prompt;

    // Prompt optimization pass
    if (optimizeMode && prompt.trim()) {
      try {
        const optimized = await optimizePrompt({ prompt });
        finalPrompt = optimized.optimized_prompt;
      } catch {
        // Non-fatal — continue with original prompt
      }
    }

    const attachmentItems = attachments.map((a) => ({
      file_id: a.file_id,
      usage_role: "primary" as const,
      transform_mode: "auto" as const,
    }));

    try {
      if (mode === "compare") {
        // Compare mode — use non-streaming endpoint
        const activeKeys = Array.from(new Set(compareModelKeys.filter(Boolean)));
        if (activeKeys.length < 2) {
          setError("Select at least 2 models to compare.");
          setStreaming(false);
          return;
        }

        const targets = activeKeys
          .map((key) => {
            const { provider, model } = parseModelKey(key);
            return { provider, model: model || undefined };
          })
          .filter((target) => target.provider);

        if (targets.length < 2) {
          setError("Choose at least 2 valid models to compare.");
          setStreaming(false);
          return;
        }

        const req: CompareRequest = {
          prompt: finalPrompt,
          targets,
          routing: { smart_mode: false, research_mode: researchMode },
          attachments: attachmentItems.length > 0 ? attachmentItems : undefined,
          context: sessionId
            ? { session_id: sessionId }
            : undefined,
        };

        const result = await sendCompare(req);
        setResponses(result.responses);
        if (result.session_id) setSessionId(result.session_id);
        setStreaming(false);
      } else {
        // Single / smart mode — streaming SSE
        const { provider, model } = parseModelKey(selectedModelKey);
        const req: ChatRequest = {
          prompt: finalPrompt,
          provider: smartMode ? undefined : provider || undefined,
          model: smartMode ? undefined : model || undefined,
          routing: { smart_mode: smartMode, research_mode: researchMode },
          attachments: attachmentItems.length > 0 ? attachmentItems : undefined,
          context: sessionId
            ? { session_id: sessionId }
            : undefined,
        };

        let finalResponse: Partial<ChatResponse> = {};

        for await (const chunk of streamChat(req, controller.signal)) {
          if (controller.signal.aborted) break;

          if (chunk.type === "delta" && chunk.text) {
            appendStreamingText(chunk.text);
          } else if (chunk.type === "metadata" && chunk.metadata) {
            finalResponse = { ...finalResponse, ...chunk.metadata };
          } else if (chunk.type === "done") {
            break;
          } else if (chunk.type === "error") {
            throw new Error(chunk.error ?? "Stream error");
          }
        }

        if (!controller.signal.aborted) {
          // Build a synthetic ChatResponse from accumulated stream data
          const streamingText = useChatStore.getState().streamingText;
          const syntheticResponse: ChatResponse = {
            request_id: finalResponse.request_id ?? crypto.randomUUID(),
            session_id: finalResponse.session_id ?? sessionId ?? undefined,
            text: streamingText,
            provider: finalResponse.provider ?? (provider || "auto"),
            model: finalResponse.model ?? (model || ""),
            latency_ms: finalResponse.latency_ms ?? 0,
            token_usage: finalResponse.token_usage ?? {
              prompt_tokens: 0,
              completion_tokens: 0,
              total_tokens: 0,
            },
            estimated_cost: finalResponse.estimated_cost ?? 0,
            cost_currency: finalResponse.cost_currency ?? "USD",
            finish_reason: finalResponse.finish_reason,
            error: finalResponse.error,
            web_source_items: finalResponse.web_source_items ?? [],
            timestamp: finalResponse.timestamp ?? new Date().toISOString(),
          };

          if (syntheticResponse.session_id) setSessionId(syntheticResponse.session_id);
          setResponses([syntheticResponse]);
        }

        setStreaming(false);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      setStreaming(false);
    }
  }, [store]);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    store.setStreaming(false);
  }, [store]);

  return { submit, cancel };
}
