import { useCallback, useRef } from "react";
import { ApiClientError } from "../api/client";
import { streamChat } from "../api/chat";
import { streamCompare } from "../api/compare";
import { fetchHistory } from "../api/history";
import { optimizePrompt } from "../api/optimize";
import {
  buildOptimizeRequest,
  cancelledOptimization,
  pendingOptimization,
  resolveOptimizationFailure,
  resolveOptimizationResponse,
} from "../optimization/promptOptimization";
import { makePlaceholderResponse, useChatStore } from "../store/chatStore";
import { parseModelKey } from "./useSmartRouting";
import type {
  AttachmentRequestItem,
  ChatRequest,
  ChatResponse,
  ChatTurn,
  CompareRequest,
  ConversationHistoryItem,
  FileUploadResponse,
  PromptOptimizationState,
  UserContextRequest,
} from "../types";

export function useChat() {
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(async () => {
    const state = useChatStore.getState();
    const rawPrompt = state.prompt.trim();
    const attachments = [...state.attachments];
    if (!rawPrompt && attachments.length === 0) return;
    if (state.mode === "compare" && state.compareModelKeys.filter(Boolean).length < 2) {
      state.setError("Select at least two models to compare.");
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    state.setError(null);
    state.setStreamingText("");

    let finalPrompt = rawPrompt;
    let turnId: string | undefined;
    let optimization: PromptOptimizationState | undefined;
    const attachmentItems = toAttachmentItems(attachments);
    const conversationHistory = buildConversationHistory(state.turns);
    const context = buildContext({
      sessionId: state.sessionId,
      pendingNewSession: state.pendingNewSession,
      conversationHistory,
    });

    try {
      if (state.optimizeMode && rawPrompt) {
        optimization = pendingOptimization(rawPrompt);
        turnId = state.beginTurn({
          mode: state.mode,
          prompt: rawPrompt,
          submittedPrompt: rawPrompt,
          attachments,
          responses: [],
          status: "optimizing",
          optimization,
        });
        state.setPrompt("");
        state.clearAttachments();

        try {
          const optimized = await optimizePrompt(
            buildOptimizeRequest({
              prompt: rawPrompt,
              conversationHistory,
              context,
              attachments,
            }),
            controller.signal,
          );
          if (controller.signal.aborted) return;
          const resolved = resolveOptimizationResponse(optimized, rawPrompt);
          finalPrompt = resolved.finalPrompt;
          optimization = resolved.optimization;
        } catch (err) {
          if (controller.signal.aborted) return;
          console.warn("Prompt optimization failed; continuing with original prompt", err);
          const resolved = resolveOptimizationFailure(rawPrompt);
          finalPrompt = resolved.finalPrompt;
          optimization = resolved.optimization;
        }

        useChatStore.getState().setTurnOptimization(turnId, optimization);
      }

      if (state.mode === "compare") {
        await runCompareTurn({
          prompt: finalPrompt,
          submittedPrompt: finalPrompt,
          context,
          attachmentItems,
          attachments,
          signal: controller.signal,
          turnId,
          optimization,
        });
      } else {
        await runAskTurn({
          prompt: finalPrompt,
          submittedPrompt: finalPrompt,
          context,
          attachmentItems,
          attachments,
          signal: controller.signal,
          turnId,
          optimization,
        });
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      const latest = useChatStore.getState();
      if (latest.activeTurnId) latest.setTurnStatus(latest.activeTurnId, "error");
      latest.setError(toFriendlyError(err));
      latest.setStreaming(false);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    const state = useChatStore.getState();
    if (state.activeTurnId) {
      const activeTurn = state.turns.find((turn) => turn.id === state.activeTurnId);
      if (activeTurn?.status === "optimizing" && activeTurn.optimization) {
        state.setTurnOptimization(
          state.activeTurnId,
          cancelledOptimization(activeTurn.optimization.originalPrompt),
        );
      }
      state.setTurnStatus(state.activeTurnId, "cancelled");
    }
    state.setStreaming(false);
  }, []);

  return { submit, cancel };
}

async function runAskTurn({
  prompt,
  submittedPrompt,
  context,
  attachmentItems,
  attachments,
  signal,
  turnId,
  optimization,
}: {
  prompt: string;
  submittedPrompt: string;
  context: UserContextRequest;
  attachmentItems: AttachmentRequestItem[];
  attachments: FileUploadResponse[];
  signal: AbortSignal;
  turnId?: string;
  optimization?: PromptOptimizationState;
}) {
  const state = useChatStore.getState();
  const { provider, model } = parseModelKey(state.selectedModelKey);
  const request: ChatRequest = {
    prompt: submittedPrompt,
    provider: state.smartMode ? undefined : provider || undefined,
    model: state.smartMode ? undefined : model || undefined,
    routing: { smart_mode: state.smartMode, research_mode: state.researchMode },
    attachments: attachmentItems.length > 0 ? attachmentItems : undefined,
    context,
  };

  const placeholder = makePlaceholderResponse(0, state.smartMode ? "smart" : provider, model, state.sessionId);
  const activeTurnId =
    turnId ??
    state.beginTurn({
      mode: "single",
      prompt,
      submittedPrompt,
      attachments,
      responses: [placeholder],
    });
  if (turnId) {
    state.prepareTurnForStreaming(turnId, {
      prompt,
      submittedPrompt,
      responses: [placeholder],
      optimization,
    });
  } else {
    state.setPrompt("");
    state.clearAttachments();
  }

  let finalResponse: Partial<ChatResponse> = {};
  for await (const chunk of streamChat(request, signal)) {
    if (signal.aborted) break;
    const latest = useChatStore.getState();
    if (chunk.type === "delta" && chunk.text) {
      latest.appendStreamingText(chunk.text);
      latest.appendTurnResponseText(activeTurnId, 0, chunk.text);
    } else if (chunk.type === "metadata" && chunk.metadata) {
      finalResponse = { ...finalResponse, ...chunk.metadata };
      latest.updateTurnResponse(activeTurnId, 0, {
        ...makePlaceholderResponse(0, provider, model, latest.sessionId),
        ...finalResponse,
        text: chunk.metadata.text ?? latest.responses[0]?.text ?? "",
      } as ChatResponse);
    } else if (chunk.type === "done") {
      if (chunk.session_id) latest.setSessionId(chunk.session_id);
      break;
    } else if (chunk.type === "error") {
      throw new Error(chunk.error ?? "Stream error");
    }
  }

  const latest = useChatStore.getState();
  if (!signal.aborted) {
    const current = latest.responses[0] ?? placeholder;
    latest.updateTurnResponse(activeTurnId, 0, {
      ...current,
      ...finalResponse,
      text: finalResponse.text ?? current.text,
      session_id: finalResponse.session_id ?? latest.sessionId ?? current.session_id,
    });
    const resolvedSession = finalResponse.session_id ?? latest.responses[0]?.session_id;
    if (resolvedSession) latest.setSessionId(resolvedSession);
    latest.setTurnStatus(activeTurnId, "complete");
    latest.setStreaming(false);
    await refreshHistory();
  }
}

async function runCompareTurn({
  prompt,
  submittedPrompt,
  context,
  attachmentItems,
  attachments,
  signal,
  turnId,
  optimization,
}: {
  prompt: string;
  submittedPrompt: string;
  context: UserContextRequest;
  attachmentItems: AttachmentRequestItem[];
  attachments: FileUploadResponse[];
  signal: AbortSignal;
  turnId?: string;
  optimization?: PromptOptimizationState;
}) {
  const state = useChatStore.getState();
  const activeKeys = state.compareModelKeys.filter(Boolean);
  if (activeKeys.length < 2) {
    state.setError("Select at least two models to compare.");
    state.setStreaming(false);
    return;
  }

  const targets = activeKeys.map((key) => {
    const { provider, model } = parseModelKey(key);
    return { provider, model: model || undefined };
  });
  const placeholders = targets.map((target, index) =>
    makePlaceholderResponse(index, target.provider, target.model ?? "", state.sessionId),
  );
  const request: CompareRequest = {
    prompt: submittedPrompt,
    targets,
    routing: { smart_mode: false, research_mode: state.compareResearchMode },
    attachments: attachmentItems.length > 0 ? attachmentItems : undefined,
    context,
  };

  const activeTurnId =
    turnId ??
    state.beginTurn({
      mode: "compare",
      prompt,
      submittedPrompt,
      attachments,
      responses: placeholders,
    });
  if (turnId) {
    state.prepareTurnForStreaming(turnId, {
      prompt,
      submittedPrompt,
      responses: placeholders,
      optimization,
    });
  } else {
    state.setPrompt("");
    state.clearAttachments();
  }

  for await (const chunk of streamCompare(request, signal)) {
    if (signal.aborted) break;
    const latest = useChatStore.getState();
    const index = chunk.index ?? 0;
    if (chunk.type === "response_start") {
      latest.appendTurnResponseText(activeTurnId, index, "", {
        provider: chunk.provider ?? latest.responses[index]?.provider ?? targets[index]?.provider ?? "",
        model: chunk.model ?? latest.responses[index]?.model ?? targets[index]?.model ?? "",
      });
    } else if (chunk.type === "delta" && chunk.text) {
      latest.appendTurnResponseText(activeTurnId, index, chunk.text);
    } else if (chunk.type === "response_done" && chunk.response) {
      latest.updateTurnResponse(activeTurnId, index, chunk.response);
    } else if (chunk.type === "done") {
      if (chunk.compare) latest.setTurnCompareSummary(activeTurnId, chunk.compare);
      if (chunk.session_id) latest.setSessionId(chunk.session_id);
      break;
    } else if (chunk.type === "error") {
      throw new Error(chunk.error ?? "Compare stream error");
    }
  }

  const latest = useChatStore.getState();
  if (!signal.aborted) {
    latest.setTurnStatus(activeTurnId, "complete");
    latest.setStreaming(false);
    await refreshHistory();
  }
}

function buildContext({
  sessionId,
  pendingNewSession,
  conversationHistory,
}: {
  sessionId: string | null;
  pendingNewSession: boolean;
  conversationHistory: ConversationHistoryItem[];
}): UserContextRequest {
  return {
    session_id: pendingNewSession ? undefined : sessionId ?? undefined,
    conversation_history: conversationHistory.length > 0 ? conversationHistory : undefined,
    new_session: pendingNewSession || !sessionId,
  };
}

export function buildConversationHistory(turns: ChatTurn[]): ConversationHistoryItem[] {
  const messages: ConversationHistoryItem[] = [];
  for (const turn of turns) {
    if (
      turn.status === "streaming" ||
      turn.status === "optimizing" ||
      turn.status === "cancelled"
    ) {
      continue;
    }
    const prompt = turn.submittedPrompt || turn.prompt;
    if (prompt) messages.push({ role: "user", content: prompt });
    const responseText = turn.responses
      .map((response) => response.text)
      .filter(Boolean)
      .join("\n\n");
    if (responseText) messages.push({ role: "assistant", content: responseText });
  }
  return messages.slice(-10);
}

function toAttachmentItems(attachments: FileUploadResponse[]): AttachmentRequestItem[] {
  return attachments.map((attachment) => ({
    file_id: attachment.file_id,
    usage_role: "primary",
    transform_mode: "auto",
  }));
}

async function refreshHistory() {
  const state = useChatStore.getState();
  try {
    const entries = await fetchHistory(500);
    state.setHistory(entries);
  } catch (err) {
    console.warn("History refresh failed", err);
  }
}

function toFriendlyError(err: unknown): string {
  if (err instanceof DOMException && err.name === "AbortError") return "Request cancelled.";
  if (err instanceof ApiClientError) {
    const detail = getDetailRecord(err.body);
    const code = typeof detail?.code === "string" ? detail.code : "";
    if (err.status === 403 && code === "session_auth_required") {
      return "Your session is not ready. Sign in or enable the local dev session, then try again.";
    }
    if (code === "attachments_require_db") {
      return "Attachments require the database-backed backend. Start the full app with PostgreSQL enabled.";
    }
    if (code === "no_attachment_compatible_provider") {
      return "The selected model cannot use the attached files. Switch models or remove the attachment.";
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "An unexpected error occurred.";
}

function getDetailRecord(body: unknown): Record<string, unknown> | null {
  if (typeof body !== "object" || body === null) return null;
  const detail = (body as Record<string, unknown>).detail;
  return typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : null;
}
