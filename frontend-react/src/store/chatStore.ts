import { create } from "zustand";
import type {
  ChatMode,
  ChatResponse,
  ChatTurn,
  CompareResponse,
  FileUploadResponse,
  HistoryEntry,
  HistoryThread,
  PromptOptimizationState,
  ResponseRunStatus,
  TurnStatus,
} from "../types";
import { buildTurnsFromHistoryEntries } from "../history/historyThreads";

interface BeginTurnInput {
  mode: ChatMode;
  prompt: string;
  submittedPrompt: string;
  researchEnabled?: boolean;
  optimizeEnabled?: boolean;
  attachments: FileUploadResponse[];
  responses: ChatResponse[];
  status?: TurnStatus;
  optimization?: PromptOptimizationState;
}

interface PrepareTurnInput {
  prompt: string;
  submittedPrompt: string;
  responses: ChatResponse[];
  optimization?: PromptOptimizationState;
}

interface ChatStoreState {
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;

  smartMode: boolean;
  researchMode: boolean;
  compareResearchMode: boolean;
  optimizeMode: boolean;
  setSmartMode: (v: boolean) => void;
  setResearchMode: (v: boolean) => void;
  setCompareResearchMode: (v: boolean) => void;
  setOptimizeMode: (v: boolean) => void;

  selectedModelKey: string;
  setSelectedModelKey: (key: string) => void;
  compareModelKeys: [string, string, string];
  setCompareModelKey: (index: 0 | 1 | 2, key: string) => void;

  prompt: string;
  setPrompt: (prompt: string) => void;

  attachments: FileUploadResponse[];
  addAttachment: (file: FileUploadResponse) => void;
  updateAttachment: (file: FileUploadResponse) => void;
  removeAttachment: (fileId: string) => void;
  clearAttachments: () => void;

  turns: ChatTurn[];
  activeTurnId: string | null;
  beginTurn: (input: BeginTurnInput) => string;
  prepareTurnForStreaming: (turnId: string, input: PrepareTurnInput) => void;
  setTurnOptimization: (turnId: string, optimization: PromptOptimizationState) => void;
  updateTurnResponse: (turnId: string, index: number, response: ChatResponse) => void;
  appendTurnResponseText: (
    turnId: string,
    index: number,
    text: string,
    patch?: Partial<ChatResponse>,
  ) => void;
  setTurnStatus: (turnId: string, status: TurnStatus) => void;
  setTurnCompareSummary: (turnId: string, summary: CompareResponse) => void;
  hydrateFromHistoryThread: (thread: HistoryThread) => void;
  startNewChat: () => void;

  responses: ChatResponse[];
  setResponses: (responses: ChatResponse[]) => void;
  appendResponse: (response: ChatResponse) => void;
  clearResponses: () => void;

  streaming: boolean;
  streamingText: string;
  setStreaming: (v: boolean) => void;
  setStreamingText: (text: string) => void;
  appendStreamingText: (chunk: string) => void;

  error: string | null;
  setError: (err: string | null) => void;

  history: HistoryEntry[];
  setHistory: (entries: HistoryEntry[]) => void;
  historySearch: string;
  setHistorySearch: (q: string) => void;

  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  pendingNewSession: boolean;
  setPendingNewSession: (v: boolean) => void;
}

export const useChatStore = create<ChatStoreState>((set) => ({
  mode: "single",
  setMode: (mode) => set({ mode }),

  smartMode: true,
  researchMode: true,
  compareResearchMode: true,
  optimizeMode: false,
  setSmartMode: (v) => set({ smartMode: v }),
  setResearchMode: (v) => set({ researchMode: v }),
  setCompareResearchMode: (v) => set({ compareResearchMode: v }),
  setOptimizeMode: (v) => set({ optimizeMode: v }),

  selectedModelKey: "",
  setSelectedModelKey: (key) => set({ selectedModelKey: key }),
  compareModelKeys: ["", "", ""],
  setCompareModelKey: (index, key) =>
    set((state) => {
      const updated = [...state.compareModelKeys] as [string, string, string];
      updated[index] = key;
      // On removal, compact: shift non-empty values to the front, empty slots to the back
      if (!key) {
        const compacted = updated.filter(Boolean);
        while (compacted.length < 3) compacted.push("");
        return { compareModelKeys: compacted as [string, string, string] };
      }
      return { compareModelKeys: updated };
    }),

  prompt: "",
  setPrompt: (prompt) => set({ prompt }),

  attachments: [],
  addAttachment: (file) =>
    set((state) => ({
      attachments: state.attachments.some((item) => item.file_id === file.file_id)
        ? state.attachments
        : [...state.attachments, file],
    })),
  updateAttachment: (file) =>
    set((state) => ({
      attachments: state.attachments.map((item) =>
        item.file_id === file.file_id ? { ...item, ...file } : item,
      ),
    })),
  removeAttachment: (fileId) =>
    set((state) => ({
      attachments: state.attachments.filter((a) => a.file_id !== fileId),
    })),
  clearAttachments: () => set({ attachments: [] }),

  turns: [],
  activeTurnId: null,
  beginTurn: (input) => {
    const id = makeId();
    const turn: ChatTurn = {
      id,
      mode: input.mode,
      prompt: input.prompt,
      submittedPrompt: input.submittedPrompt,
      researchEnabled: input.researchEnabled,
      optimizeEnabled: input.optimizeEnabled,
      attachments: input.attachments,
      responses: input.responses,
      status: input.status ?? "streaming",
      createdAt: new Date().toISOString(),
      optimization: input.optimization,
    };
    set((state) => ({
      turns: [...state.turns, turn],
      activeTurnId: id,
      responses: input.responses,
      streaming: turn.status === "optimizing" || turn.status === "streaming",
      streamingText: "",
      error: null,
    }));
    return id;
  },
  prepareTurnForStreaming: (turnId, input) =>
    set((state) => {
      const turns = state.turns.map((turn) =>
        turn.id === turnId
          ? {
              ...turn,
              prompt: input.prompt,
              submittedPrompt: input.submittedPrompt,
              responses: input.responses,
              status: "streaming" as const,
              optimization: input.optimization ?? turn.optimization,
            }
          : turn,
      );
      return {
        turns,
        responses: state.activeTurnId === turnId ? input.responses : state.responses,
        streaming: true,
        streamingText: "",
      };
    }),
  setTurnOptimization: (turnId, optimization) =>
    set((state) => ({
      turns: state.turns.map((turn) =>
        turn.id === turnId ? { ...turn, optimization } : turn,
      ),
    })),
  updateTurnResponse: (turnId, index, response) =>
    set((state) => updateResponseState(state, turnId, index, () => response)),
  appendTurnResponseText: (turnId, index, text, patch) =>
    set((state) =>
      updateResponseState(state, turnId, index, (current) => ({
        ...current,
        ...patch,
        text: `${current.text}${text}`,
      })),
    ),
  setTurnStatus: (turnId, status) =>
    set((state) => ({
      turns: state.turns.map((turn) => (turn.id === turnId ? { ...turn, status } : turn)),
      streaming:
        status === "optimizing" || status === "streaming"
          ? true
          : state.activeTurnId === turnId
            ? false
            : state.streaming,
    })),
  setTurnCompareSummary: (turnId, summary) =>
    set((state) => {
      let activeResponses = state.responses;
      const turns = state.turns.map((turn) => {
        if (turn.id !== turnId) return turn;
        const responses = mergeCompletedResponses(turn.responses, summary.responses);
        if (state.activeTurnId === turnId) activeResponses = responses;
        return {
          ...turn,
          requestGroupId: summary.request_group_id,
          compareSummary: { ...summary, responses },
          responses,
        };
      });
      return {
        turns,
        responses: state.activeTurnId === turnId ? activeResponses : state.responses,
      };
    }),
  hydrateFromHistoryThread: (thread) => {
    const turns = buildTurnsFromHistoryEntries(thread.entries);
    const latestTurn = turns[turns.length - 1] ?? null;
    set({
      mode: latestTurn?.mode ?? thread.preferredMode,
      prompt: "",
      attachments: [],
      activeTurnId: latestTurn?.id ?? null,
      turns,
      responses: latestTurn?.responses ?? [],
      streaming: false,
      streamingText: "",
      sessionId: thread.sessionId ?? null,
      pendingNewSession: !thread.sessionId,
      error: null,
    });
  },
  startNewChat: () =>
    set({
      prompt: "",
      attachments: [],
      turns: [],
      activeTurnId: null,
      responses: [],
      streamingText: "",
      streaming: false,
      error: null,
      sessionId: null,
      pendingNewSession: true,
    }),

  responses: [],
  setResponses: (responses) => set({ responses }),
  appendResponse: (response) => set((state) => ({ responses: [...state.responses, response] })),
  clearResponses: () => set({ responses: [], streamingText: "", streaming: false, turns: [] }),

  streaming: false,
  streamingText: "",
  setStreaming: (v) => set({ streaming: v }),
  setStreamingText: (text) => set({ streamingText: text }),
  appendStreamingText: (chunk) =>
    set((state) => ({ streamingText: state.streamingText + chunk })),

  error: null,
  setError: (err) => set({ error: err }),

  history: [],
  setHistory: (entries) => set({ history: entries }),
  historySearch: "",
  setHistorySearch: (q) => set({ historySearch: q }),

  sessionId: null,
  setSessionId: (id) => set({ sessionId: id, pendingNewSession: false }),
  pendingNewSession: true,
  setPendingNewSession: (v) => set({ pendingNewSession: v }),
}));

export function makePlaceholderResponse(
  index: number,
  provider: string,
  model: string,
  sessionId?: string | null,
  options: { status?: ResponseRunStatus; startedAt?: string } = {},
): ChatResponse {
  const timestamp = new Date().toISOString();
  const startedAt = options.startedAt ?? timestamp;
  return {
    request_id: makeId(`pending-${index}`),
    session_id: sessionId ?? undefined,
    text: "",
    provider: provider || "auto",
    model: model || "Working",
    latency_ms: null,
    token_usage: null,
    estimated_cost: 0,
    cost_currency: "USD",
    web_source_items: [],
    timestamp,
    ui_status: options.status ?? "queued",
    started_at: startedAt,
  };
}

type StoreSnapshot = Pick<ChatStoreState, "turns" | "activeTurnId" | "responses" | "streaming">;

function updateResponseState(
  state: StoreSnapshot,
  turnId: string,
  index: number,
  updater: (current: ChatResponse) => ChatResponse,
) {
  const turns = state.turns.map((turn) => {
    if (turn.id !== turnId) return turn;
    const responses = [...turn.responses];
    const current = responses[index] ?? makePlaceholderResponse(index, "", "", undefined);
    responses[index] = updater(current);
    return { ...turn, responses };
  });

  const active = turns.find((turn) => turn.id === state.activeTurnId);
  return {
    turns,
    responses: state.activeTurnId === turnId ? active?.responses ?? state.responses : state.responses,
  };
}

function mergeCompletedResponses(
  existing: ChatResponse[],
  completed: ChatResponse[],
): ChatResponse[] {
  const resolvedAt = new Date().toISOString();
  return completed.map((response, index) => {
    const previous = existing[index];
    const failed = !!response.error;
    return {
      ...response,
      started_at: previous?.started_at ?? response.started_at,
      completed_at: failed
        ? response.completed_at ?? previous?.completed_at
        : response.completed_at ?? previous?.completed_at ?? resolvedAt,
      failed_at: failed
        ? response.failed_at ?? previous?.failed_at ?? resolvedAt
        : response.failed_at,
      ui_status: failed ? "failed" : "complete",
    };
  });
}

function makeId(prefix = "turn"): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${random}`;
}
