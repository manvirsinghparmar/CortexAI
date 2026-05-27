import { useRef, useEffect, useCallback } from "react";
import { ModelSelector } from "./ModelSelector";
import { CompareSelector } from "./CompareSelector";
import { FeatureChips } from "./FeatureChips";
import { AttachmentStrip } from "./AttachmentStrip";
import { useChatStore } from "../../store/chatStore";
import { useChat } from "../../hooks/useChat";
import { isModelDropdownVisible } from "../../hooks/useSmartRouting";
import type { ModelCatalogItem } from "../../types";
import { DEFAULT_MODELS } from "../../config/defaultModels";
import styles from "./PromptComposer.module.css";

interface PromptComposerProps {
  models: ModelCatalogItem[];
}

export function PromptComposer({ models }: PromptComposerProps) {
  const availableModels = models.length > 0 ? models : DEFAULT_MODELS;
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

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [prompt, resize]);

  useEffect(() => {
    if (availableModels.length >= 2) {
      if (!compareModelKeys[0]) {
        setCompareModelKey(0, `${availableModels[0]!.provider}:${availableModels[0]!.model}`);
      }
      if (!compareModelKeys[1]) {
        setCompareModelKey(1, `${availableModels[1]!.provider}:${availableModels[1]!.model}`);
      }
      if (!selectedModelKey) {
        setSelectedModelKey(`${availableModels[0]!.provider}:${availableModels[0]!.model}`);
      }
    }
  }, [availableModels, compareModelKeys, selectedModelKey, setCompareModelKey, setSelectedModelKey]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!streaming && prompt.trim()) void submit();
    }
  };

  const showModelDropdown = isModelDropdownVisible(mode, smartMode);

  return (
    <div className={`${styles.card} ${mode === "single" ? styles.askCard : ""}`}>
      <div className={styles.modelRow}>
        {mode === "compare" ? (
          <CompareSelector
            models={availableModels}
            keys={compareModelKeys}
            onChange={setCompareModelKey}
          />
        ) : (
          <>
            {showModelDropdown && (
              <ModelSelector
                id="singleModel"
                label="Using"
                models={availableModels}
                value={selectedModelKey}
                onChange={setSelectedModelKey}
              />
            )}
            <FeatureChips
              smartMode={smartMode}
              researchMode={researchMode}
              optimizeMode={optimizeMode}
              onSmartToggle={setSmartMode}
              onResearchToggle={setResearchMode}
              onOptimizeToggle={setOptimizeMode}
            />
          </>
        )}
      </div>

      <div className={styles.inputRow}>
        <AttachmentStrip />
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          rows={1}
          aria-label="Prompt input"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          placeholder={
            mode === "compare"
              ? "Ask anything to compare models..."
              : "Describe your technical problem or paste a snippet..."
          }
        />

        <div className={styles.actions}>
          <label className={styles.compareSwitch}>
            <span>Compare</span>
            <input
              type="checkbox"
              checked={mode === "compare"}
              onChange={(event) => setMode(event.target.checked ? "compare" : "single")}
            />
            <span className={styles.switchTrack} aria-hidden="true" />
          </label>
          <button
            className={styles.submitButton}
            type="button"
            aria-label={streaming ? "Stop" : "Send message"}
            onClick={() => (streaming ? cancel() : void submit())}
            disabled={!streaming && !prompt.trim()}
          >
            {streaming ? <span className={styles.stopIcon} /> : <SendIcon />}
          </button>
        </div>
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h13" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}
