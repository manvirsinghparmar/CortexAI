import { useMemo } from "react";
import { useChatStore } from "../../store/chatStore";
import { useHistory } from "../../hooks/useHistory";
import type { HistoryEntry, WhoAmIResponse } from "../../types";

interface SidebarProps {
  onSelectEntry: (entry: HistoryEntry) => void;
  whoAmI?: WhoAmIResponse | null;
  loggedIn?: boolean;
  onLogin?: () => void;
  onLogout?: () => void;
}

export function Sidebar({ onSelectEntry, whoAmI, loggedIn, onLogin, onLogout }: SidebarProps) {
  const history = useChatStore((s) => s.history);
  const historySearch = useChatStore((s) => s.historySearch);
  const setHistorySearch = useChatStore((s) => s.setHistorySearch);
  const setHistory = useChatStore((s) => s.setHistory);
  const sessionId = useChatStore((s) => s.sessionId);
  const { clear } = useHistory();

  const filtered = useMemo(() => {
    const q = historySearch.trim().toLowerCase();
    if (!q) return history;
    return history.filter(
      (e) =>
        e.prompt.toLowerCase().includes(q) || e.response.toLowerCase().includes(q),
    );
  }, [history, historySearch]);

  const handleClearAll = async () => {
    if (!window.confirm("Clear all chat history?")) return;
    await clear(sessionId ?? undefined);
    setHistory([]);
  };

  const handleNewChat = () => {
    useChatStore.setState({
      prompt: "",
      responses: [],
      streamingText: "",
      streaming: false,
      error: null,
    });
  };

  const userInitial = (whoAmI?.user_id ?? "U")[0]?.toUpperCase() ?? "U";
  const userLabel = whoAmI?.user_id ?? "Guest";

  return (
    <aside
      className="flex flex-col w-64 shrink-0 h-screen bg-zinc-900 dark:bg-zinc-950 text-white"
      aria-label="Sidebar"
    >
      {/* Logo */}
      <div className="px-5 pt-6 pb-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-white flex items-center justify-center">
            <span className="text-zinc-900 text-xs font-bold">C</span>
          </div>
          <div>
            <div className="text-sm font-semibold leading-none">CortexAI</div>
            <div className="text-xs text-zinc-500 leading-none mt-0.5">Gateway</div>
          </div>
        </div>
      </div>

      {/* New Chat button */}
      <div className="px-3 pt-3">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 20H5a1 1 0 0 1-1-1v-7" />
            <path d="M20.65 7.35a2.1 2.1 0 0 0-2.97-2.97L8 14.06V18h3.94l8.71-8.65Z" />
          </svg>
          New chat
        </button>
      </div>

      {/* History section */}
      <div className="flex flex-col flex-1 overflow-hidden px-3 pt-3">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">History</span>
          {history.length > 0 && (
            <button
              onClick={handleClearAll}
              className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500 pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            className="w-full bg-zinc-800 text-zinc-200 placeholder-zinc-500 text-xs rounded-md pl-8 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            placeholder="Search history"
            aria-label="Search history"
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
          />
        </div>

        {/* History list */}
        <div className="flex-1 overflow-y-auto -mx-1 px-1">
          {filtered.length === 0 ? (
            <div className="text-center text-zinc-600 text-xs py-8 px-2">
              <svg className="w-5 h-5 mx-auto mb-2 text-zinc-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              No history yet.<br />Send a prompt to start.
            </div>
          ) : (
            <ul role="list" className="space-y-0.5">
              {filtered.map((entry) => (
                <li key={entry.id} role="listitem">
                  <button
                    className="w-full text-left px-2 py-2 rounded-lg hover:bg-zinc-800 transition-colors group"
                    onClick={() => onSelectEntry(entry)}
                    title={entry.prompt}
                  >
                    <div className="text-xs text-zinc-300 truncate group-hover:text-white leading-snug">
                      {entry.prompt}
                    </div>
                    <div className="text-[10px] text-zinc-600 mt-0.5">
                      {new Date(entry.timestamp).toLocaleDateString()} · {entry.provider}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* User profile at bottom */}
      <div className="border-t border-zinc-800 px-4 py-3">
        {loggedIn && whoAmI ? (
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-200 shrink-0">
              {userInitial}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-zinc-300 truncate">{userLabel}</div>
            </div>
            {onLogout && (
              <button
                onClick={onLogout}
                className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors shrink-0"
              >
                Sign out
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center text-xs text-zinc-500 shrink-0">
              {userInitial}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-zinc-500">Guest</div>
            </div>
            {onLogin && (
              <button
                onClick={onLogin}
                className="text-[10px] text-zinc-400 hover:text-white transition-colors shrink-0"
              >
                Sign in
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
