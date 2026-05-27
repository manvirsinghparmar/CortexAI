import type { ChatMode } from "../../types";

interface ModeToggleProps {
  mode: ChatMode;
  onChange: (mode: ChatMode) => void;
}

// Mode toggle is now rendered as the Ask/Compare tab bar in ChatPage.
// This component is kept for backward compatibility only.
export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="flex gap-0.5 bg-zinc-100 dark:bg-zinc-800 rounded-lg p-1" role="tablist" aria-label="Chat mode">
      <button
        className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${mode === "single" ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm" : "text-zinc-500 dark:text-zinc-400"}`}
        role="tab"
        aria-selected={mode === "single"}
        onClick={() => onChange("single")}
      >
        Ask
      </button>
      <button
        className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${mode === "compare" ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white shadow-sm" : "text-zinc-500 dark:text-zinc-400"}`}
        role="tab"
        aria-selected={mode === "compare"}
        onClick={() => onChange("compare")}
      >
        Compare
      </button>
    </div>
  );
}
