import { get, del, patch } from "./client";
import type { HistoryEntry } from "../types";

export async function fetchHistory(limit = 100, sessionId?: string): Promise<HistoryEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (sessionId) params.set("session_id", sessionId);
  return get<HistoryEntry[]>(`/v1/history?${params.toString()}`);
}

export async function deleteHistoryEntry(id: number): Promise<void> {
  await del<unknown>(`/v1/history/${id}`);
}

export async function clearHistory(sessionId?: string): Promise<void> {
  const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  await del<unknown>(`/v1/history${params}`);
}

export async function renameHistorySession(
  sessionId: string,
  title: string,
): Promise<{ session_id: string; title: string }> {
  return patch<{ session_id: string; title: string }>(
    `/v1/history/session/${encodeURIComponent(sessionId)}`,
    { title },
  );
}
