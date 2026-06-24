import type {
  ConversationHistoryItem,
  FileUploadResponse,
  OptimizeRequest,
  OptimizeResponse,
  PromptOptimizationState,
  UserContextRequest,
} from "../types";

const CONTEXT_MESSAGE_LIMIT = 10;
const CONTEXT_MESSAGE_CHARS = 500;
const CONTEXT_HINT_MAX_CHARS = 4000;

export const OPTIMIZATION_ORIGINAL_NOTE =
  "Your prompt was already clear. CortexAI sent the original version.";

export interface OptimizationResolution {
  finalPrompt: string;
  optimization: PromptOptimizationState;
}

export function buildOptimizeRequest({
  prompt,
  conversationHistory,
  context,
  attachments,
}: {
  prompt: string;
  conversationHistory: ConversationHistoryItem[];
  context: UserContextRequest;
  attachments: FileUploadResponse[];
}): OptimizeRequest {
  const request: OptimizeRequest = { prompt };

  const contextMessages = selectOptimizeContextMessages(conversationHistory);
  if (contextMessages.length === 0) return request;

  const hintPrefix =
    attachments.length > 0
      ? "Use only prior chat text to resolve references in the latest prompt; attached file contents are not included:\n"
      : "Use only to resolve references in the latest prompt:\n";
  const hintBody = contextMessages
    .map((item, index) => `Recent ${item.role} ${index + 1}: ${item.content}`)
    .join("\n")
    .slice(0, Math.max(0, CONTEXT_HINT_MAX_CHARS - hintPrefix.length))
    .trim();

  request.context = {
    session_id: context.session_id,
    conversation_history: contextMessages,
    new_session: context.new_session,
  };
  if (hintBody) request.context_hint = `${hintPrefix}${hintBody}`;
  return request;
}

export function resolveOptimizationResponse(
  response: OptimizeResponse,
  originalPrompt: string,
): OptimizationResolution {
  const optimizedPrompt = response.optimized_prompt.trim();
  const wasOptimized = response.was_optimized && optimizedPrompt.length > 0;
  const finalPrompt = wasOptimized ? optimizedPrompt : originalPrompt;
  return {
    finalPrompt,
    optimization: {
      status: wasOptimized ? "optimized" : "kept_original",
      originalPrompt,
      displayPrompt: finalPrompt,
      note: wasOptimized ? undefined : OPTIMIZATION_ORIGINAL_NOTE,
      optimizationStatus: response.optimization_status,
      fallbackReason: response.fallback_reason,
    },
  };
}

export function resolveOptimizationFailure(originalPrompt: string): OptimizationResolution {
  return {
    finalPrompt: originalPrompt,
    optimization: {
      status: "kept_original",
      originalPrompt,
      displayPrompt: originalPrompt,
      note: OPTIMIZATION_ORIGINAL_NOTE,
      optimizationStatus: "failed",
      fallbackReason: "optimization_failed",
    },
  };
}

export function pendingOptimization(originalPrompt: string): PromptOptimizationState {
  return {
    status: "pending",
    originalPrompt,
    displayPrompt: originalPrompt,
  };
}

export function cancelledOptimization(
  originalPrompt: string,
): PromptOptimizationState {
  return {
    status: "cancelled",
    originalPrompt,
    displayPrompt: "Optimization stopped.",
    optimizationStatus: "cancelled",
  };
}

export function isLikelyFollowUpPrompt(
  prompt: string,
  conversationHistory: ConversationHistoryItem[],
): boolean {
  const text = prompt.toLowerCase().replace(/\s+/g, " ").trim();
  if (!text || conversationHistory.length === 0) return false;

  const patterns = [
    /\b(i\s+(?:mean|meant|was\s+talking\s+about)|you\s+said|as\s+above|from\s+above|previous(?:ly)?|earlier|that one|same topic|the same|continue|follow[-\s]?up)\b/i,
    /\b(the above|the previous|the first one|the second one|the third one|first one|second one|third one|my last|last answer|last response|that response|this topic|same topic)\b/i,
    /^(?:who|what|why|how|where|when|how many|how much)\b.{0,120}\b(their|its)\b/i,
    /^(?:give me|provide|show me|create|make)\b.{0,120}\b(the|that|those)\s+(?:detailed\s+)?(?:range|breakdown|summary|timeline|list|comparison|estimate|estimates|details)\b/i,
    /^(?:also|and|but|so|then|what about|how about|can you|could you|make|rewrite|improve|modify|explain|list|summarize|tell me|why|what|how|where|when)\b.{0,110}\b(it|that|this|these|those|their|its|same|above|previous|earlier|first one|second one|third one)\b/i,
  ];
  return patterns.some((pattern) => pattern.test(text));
}

function selectOptimizeContextMessages(
  conversationHistory: ConversationHistoryItem[],
): ConversationHistoryItem[] {
  return conversationHistory
    .filter((item) => item.role === "user" || item.role === "assistant")
    .map((item) => ({
      role: item.role,
      content: normalizeContextText(item.content),
    }))
    .filter((item) => item.content.length > 0)
    .slice(-CONTEXT_MESSAGE_LIMIT);
}

function normalizeContextText(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, CONTEXT_MESSAGE_CHARS).trim();
}
