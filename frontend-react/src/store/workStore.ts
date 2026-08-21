import { create } from "zustand";
import type {
  ToolCatalogItem,
  ToolConnection,
  WorkApproval,
  WorkArtifact,
  WorkEvent,
  WorkRun,
  WorkSession,
} from "../types";

interface WorkStoreState {
  sessions: WorkSession[];
  session: WorkSession | null;
  run: WorkRun | null;
  events: WorkEvent[];
  artifacts: WorkArtifact[];
  approval: WorkApproval | null;
  toolCatalog: ToolCatalogItem[];
  connections: ToolConnection[];
  enabledConnectionIds: string[];
  webEnabled: boolean;
  maxCreditBudget: number;
  loading: boolean;
  streaming: boolean;
  error: string | null;
  setSessions: (sessions: WorkSession[]) => void;
  setSession: (session: WorkSession | null) => void;
  setRun: (run: WorkRun | null) => void;
  replaceEvents: (events: WorkEvent[]) => void;
  appendEvent: (event: WorkEvent) => void;
  setArtifacts: (artifacts: WorkArtifact[]) => void;
  setApproval: (approval: WorkApproval | null) => void;
  setToolCatalog: (items: ToolCatalogItem[]) => void;
  setConnections: (items: ToolConnection[]) => void;
  toggleConnection: (id: string) => void;
  setWebEnabled: (enabled: boolean) => void;
  setMaxCreditBudget: (value: number) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  resetWorkspace: () => void;
}

export const useWorkStore = create<WorkStoreState>((set) => ({
  sessions: [],
  session: null,
  run: null,
  events: [],
  artifacts: [],
  approval: null,
  toolCatalog: [],
  connections: [],
  enabledConnectionIds: [],
  webEnabled: false,
  maxCreditBudget: 100_000,
  loading: false,
  streaming: false,
  error: null,
  setSessions: (sessions) => set({ sessions }),
  setSession: (session) => set({ session }),
  setRun: (run) => set({ run }),
  replaceEvents: (events) => set({ events: dedupeEvents(events) }),
  appendEvent: (event) =>
    set((state) => ({ events: dedupeEvents([...state.events, event]) })),
  setArtifacts: (artifacts) => set({ artifacts }),
  setApproval: (approval) => set({ approval }),
  setToolCatalog: (toolCatalog) => set({ toolCatalog }),
  setConnections: (connections) => set({ connections }),
  toggleConnection: (id) =>
    set((state) => ({
      enabledConnectionIds: state.enabledConnectionIds.includes(id)
        ? state.enabledConnectionIds.filter((value) => value !== id)
        : [...state.enabledConnectionIds, id],
    })),
  setWebEnabled: (webEnabled) => set({ webEnabled }),
  setMaxCreditBudget: (maxCreditBudget) => set({ maxCreditBudget }),
  setLoading: (loading) => set({ loading }),
  setStreaming: (streaming) => set({ streaming }),
  setError: (error) => set({ error }),
  resetWorkspace: () =>
    set({
      session: null,
      run: null,
      events: [],
      artifacts: [],
      approval: null,
      enabledConnectionIds: [],
      streaming: false,
      error: null,
    }),
}));

function dedupeEvents(events: WorkEvent[]): WorkEvent[] {
  return [...new Map(events.map((event) => [event.sequence, event])).values()].sort(
    (left, right) => left.sequence - right.sequence,
  );
}
