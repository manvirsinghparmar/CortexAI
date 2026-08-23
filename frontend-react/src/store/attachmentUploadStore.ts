import { create } from "zustand";
import type { AttachmentUploadMode } from "../config/runtimeConfig";
import type { FileUploadResponse } from "../types";

export type AttachmentUploadState =
  | "authorizing"
  | "uploading"
  | "processing"
  | "ready"
  | "failed"
  | "cancelled";

export type AttachmentUploadFailureStage =
  | "authorization"
  | "upload"
  | "completion"
  | "processing";

export interface AttachmentUploadTask {
  clientId: string;
  file: File;
  fileId?: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  state: AttachmentUploadState;
  progress: number;
  error?: string;
  errorCode?: string;
  failureStage?: AttachmentUploadFailureStage;
  retryCount: number;
  uploadMode: AttachmentUploadMode;
  target?: { provider: string; model: string };
  serverFile?: FileUploadResponse;
}

interface AttachmentUploadStoreState {
  tasks: AttachmentUploadTask[];
  addTasks: (tasks: AttachmentUploadTask[]) => void;
  patchTask: (clientId: string, patch: Partial<AttachmentUploadTask>) => void;
  removeTask: (clientId: string) => void;
  clearTasks: () => void;
}

export const useAttachmentUploadStore = create<AttachmentUploadStoreState>((set) => ({
  tasks: [],
  addTasks: (tasks) =>
    set((state) => ({
      tasks: [...state.tasks, ...tasks],
    })),
  patchTask: (clientId, patch) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.clientId === clientId ? { ...task, ...patch } : task,
      ),
    })),
  removeTask: (clientId) =>
    set((state) => ({
      tasks: state.tasks.filter((task) => task.clientId !== clientId),
    })),
  clearTasks: () => set({ tasks: [] }),
}));

export function findAttachmentUploadTask(clientId: string): AttachmentUploadTask | undefined {
  return useAttachmentUploadStore.getState().tasks.find((task) => task.clientId === clientId);
}
