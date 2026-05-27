import { useRef, useEffect, useCallback } from "react";
import { ModelSelector } from "./ModelSelector";
import { CompareSelector } from "./CompareSelector";
import { FeatureChips } from "./FeatureChips";
import { AttachmentStrip } from "./AttachmentStrip";
import { useChatStore } from "../../store/chatStore";
import { useChat } from "../../hooks/useChat";
import { isModelDropdownVisible } from "../../hooks/useSmartRouting";
import type { ModelCatalogItem } from "../../types";

interface PromptComposerProps {
  models: ModelCatalogItem[];
}

export function PromptComposer({ models }: PromptComposerProps) {
  const mode = useChatStore((s) => s.mode);
  const smartMode = useChatStore((s) => s.smartMode);
  const setSmartMode = useChatStore((s) => s.setSmartMode);
  const researchMode = useChatStore((s) => s.researchMode);
  const setResearchMode = useChatStore((s) => s.setResearchMode);
  const optimizeMode = useChatStore((s) => s.optimizeMode);
  const setOptimizeMode = useChatStore((s) => s.setOptimizeMode);
  const selectedModelKey = useChatStore((s) => s.selectedModelKey);
  const setSelectedModelKey = useChatStore((s) => s.setSelectedModelKey);
  const compareModelKeys = useChatStore((s) => s.compareModelKeys);
  const setCompareModelKey = useChatStore((s) => s.setCompareModelKey);
  const prompt = useChatStore((s) => s.prompt);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const streaming = useChatStore((s) => s.streaming);

  const { submit, cancel } = useChat();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [prompt, resize]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!streaming) void submit();
    }
  };

  const showModelDropdown = isModelDropdownVisible(mode, smartMode);

  useEffect(() => {
    if (models.length >= 2) {
      if (!compareModelKeys[0])
        setCompareModelKey(0, `${models[0]!.provider}:${models[0]!.model}`);
      if (!compareModelKeys[1])
        setCompareModelKey(1, `${models[1]!.provider}:${models[1]!.model}`);
    }
  }, [models, compareModelKeys, setCompareModelKey]);

  return (
    <div className="bg-white dark:bg-zinc-800 rounded-2xl border border-zinc-200 dark:border-zinc-700 shadow-lg overflow-hidden">
      {/* Model selector row */}
      {(mode === "compare" || showModelDropdown) && (
        <div className="px-4 pt-3 pb-0">
          {mode === "single" && showModelDropdown && (
            <ModelSelector
              id="singleModel"
              label="Using:"
              models={models}
              value={selectedModelKey}
              onChange={setSelectedModelKey}
            />
          )}
          {mode === "compare" && (
            <CompareSelector
              models={models}
              keys={compareModelKeys}
              onChange={setCompareModelKey}
            />
          )}
        </div>
      )}

      {/* Textarea */}
      <div className="relative px-4 pt-3 pb-2">
        <textarea
          ref={textareaRef}
          className="w-full resize-none bg-transparent text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 text-sm leading-relaxed focus:outline-none"
          placeholder="Ask anything…"
          rows={1}
          aria-label="Prompt input"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
      </div>

      {/* Attachment strip */}
      <div className="px-4">
        <AttachmentStrip />
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between px-3 pb-3 pt-1 gap-2">
        {mode === "single" ? (
          <FeatureChips
            smartMode={smartMode}
            researchMode={researchMode}
            optimizeMode={optimizeMode}
            onSmartToggle={setSmartMode}
            onResearchToggle={setResearchMode}
            onOptimizeToggle={setOptimizeMode}
          />
        ) : (
          <div />
        )}

        {/* Send / Stop button */}
        <button
          className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-all ${
            streaming
              ? "bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-300 dark:hover:bg-zinc-600"
              : prompt.trim()
              ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-700 dark:hover:bg-zinc-300"
              : "bg-zinc-100 dark:bg-zinc-700 text-zinc-400 dark:text-zinc-500 cursor-not-allowed"
          }`}
          aria-label={streaming ? "Stop" : "Send message"}
          onClick={() => (streaming ? cancel() : void submit())}
          disabled={!streaming && !prompt.trim()}
        >
          {streaming ? (
            <span className="w-3 h-3 bg-current rounded-sm" aria-hidden="true" />
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
