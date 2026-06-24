import { useCallback } from "react";
import { fetchHistory, deleteHistoryEntry, clearHistory } from "../api/history";
import { useChatStore } from "../store/chatStore";

export function useHistory() {
  const { setHistory, setError } = useChatStore();

  const load = useCallback(
    async (sessionId?: string) => {
      try {
        const entries = await fetchHistory(500, sessionId);
        setHistory(entries);
      } catch (err) {
        console.warn("History load failed", err);
      }
    },
    [setHistory],
  );

  const remove = useCallback(
    async (id: number, sessionId?: string) => {
      try {
        await deleteHistoryEntry(id);
        await load(sessionId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete history entry");
      }
    },
    [load, setError],
  );

  const clear = useCallback(
    async (sessionId?: string) => {
      try {
        await clearHistory(sessionId);
        setHistory([]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to clear history");
      }
    },
    [setHistory, setError],
  );

  return { load, remove, clear };
}
