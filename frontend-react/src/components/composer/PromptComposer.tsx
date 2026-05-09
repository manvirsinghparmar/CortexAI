import { useRef, useEffect, useCallback } from "react";
import { ModeToggle } from "./ModeToggle";
import { ModelSelector } from "./ModelSelector";
import { CompareSelector } from "./CompareSelector";
import { FeatureChips } from "./FeatureChips";
import { AttachmentStrip } from "./AttachmentStrip";
import { useChatStore } from "../../store/chatStore";
import { useChat } from "../../hooks/useChat";
import { isModelDropdownVisible } from "../../hooks/useSmartRouting";
import type { ModelCatalogItem } from "../../types";
import styles from "./PromptComposer.module.css";

interface PromptComposerProps {
  models: ModelCatalogItem[];
}

export function PromptComposer({ models }: PromptComposerProps) {
  const mode = useChatStore((s) => s.mode);
  const setMode = useChatStore((s) => s.setMode);
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

  // Auto-resize textarea
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

  // Seed compare model keys when models load and keys are empty
  useEffect(() => {
    if (models.length >= 2) {
      if (!compareModelKeys[0])
        setCompareModelKey(0, `${models[0]!.provider}:${models[0]!.model}`);
      if (!compareModelKeys[1])
        setCompareModelKey(1, `${models[1]!.provider}:${models[1]!.model}`);
    }
  }, [models, compareModelKeys, setCompareModelKey]);

  return (
    <div className={styles.card}>
      {/* Toolbar row */}
      <div className={styles.toolbar}>
        <ModeToggle mode={mode} onChange={setMode} />

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

      {/* Input area */}
      <div className={styles.inputWrap}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder="Ask anything..."
          rows={1}
          aria-label="Prompt input"
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={streaming}
        />
        <button
          className={`${styles.submitBtn} ${streaming ? styles.stopBtn : ""}`}
          aria-label={streaming ? "Stop" : "Send message"}
          onClick={() => (streaming ? cancel() : void submit())}
        >
          {streaming ? <span className={styles.stopIcon}>■</span> : <span>↑</span>}
        </button>
      </div>

      {/* Attachment strip */}
      <AttachmentStrip />

      {/* Footer: feature chips */}
      {mode === "single" && (
        <div className={styles.footer}>
          <FeatureChips
            smartMode={smartMode}
            researchMode={researchMode}
            optimizeMode={optimizeMode}
            onSmartToggle={setSmartMode}
            onResearchToggle={setResearchMode}
            onOptimizeToggle={setOptimizeMode}
          />
        </div>
      )}
    </div>
  );
}
