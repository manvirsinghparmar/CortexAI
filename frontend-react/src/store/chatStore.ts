import { create } from "zustand";
import type { ChatResponse, HistoryEntry, FileUploadResponse, ChatMode } from "../types";

interface ChatStoreState {
  // Mode
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;

  // Routing chips
  smartMode: boolean;
  researchMode: boolean;
  optimizeMode: boolean;
  setSmartMode: (v: boolean) => void;
  setResearchMode: (v: boolean) => void;
  setOptimizeMode: (v: boolean) => void;

  // Model selection
  selectedModelKey: string; // "provider:model" or "" for auto
  setSelectedModelKey: (key: string) => void;
  compareModelKeys: [string, string, string];
  setCompareModelKey: (index: 0 | 1 | 2, key: string) => void;

  // Prompt input
  prompt: string;
  setPrompt: (prompt: string) => void;

  // Attachments
  attachments: FileUploadResponse[];
  addAttachment: (file: FileUploadResponse) => void;
  removeAttachment: (fileId: string) => void;
  clearAttachments: () => void;

  // Responses
  responses: ChatResponse[];
  setResponses: (responses: ChatResponse[]) => void;
  appendResponse: (response: ChatResponse) => void;
  clearResponses: () => void;

  // Streaming state
  streaming: boolean;
  streamingText: string;
  setStreaming: (v: boolean) => void;
  setStreamingText: (text: string) => void;
  appendStreamingText: (chunk: string) => void;

  // Error
  error: string | null;
  setError: (err: string | null) => void;

  // History
  history: HistoryEntry[];
  setHistory: (entries: HistoryEntry[]) => void;
  historySearch: string;
  setHistorySearch: (q: string) => void;

  // Active session
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
}

export const useChatStore = create<ChatStoreState>((set) => ({
  mode: "single",
  setMode: (mode) => set({ mode }),

  smartMode: true,
  researchMode: false,
  optimizeMode: false,
  setSmartMode: (v) => set({ smartMode: v }),
  setResearchMode: (v) => set({ researchMode: v }),
  setOptimizeMode: (v) => set({ optimizeMode: v }),

  selectedModelKey: "",
  setSelectedModelKey: (key) => set({ selectedModelKey: key }),
  compareModelKeys: ["", "", ""],
  setCompareModelKey: (index, key) =>
    set((state) => {
      const updated = [...state.compareModelKeys] as [string, string, string];
      updated[index] = key;
      return { compareModelKeys: updated };
    }),

  prompt: "",
  setPrompt: (prompt) => set({ prompt }),

  attachments: [],
  addAttachment: (file) =>
    set((state) => ({ attachments: [...state.attachments, file] })),
  removeAttachment: (fileId) =>
    set((state) => ({
      attachments: state.attachments.filter((a) => a.file_id !== fileId),
    })),
  clearAttachments: () => set({ attachments: [] }),

  responses: [],
  setResponses: (responses) => set({ responses }),
  appendResponse: (response) =>
    set((state) => ({ responses: [...state.responses, response] })),
  clearResponses: () => set({ responses: [], streamingText: "", streaming: false }),

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
  setSessionId: (id) => set({ sessionId: id }),
}));
