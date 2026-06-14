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
import { resolveCompareModelKeys } from "../../config/compareDefaults";
import styles from "./PromptComposer.module.css";

interface PromptComposerProps {
  models: ModelCatalogItem[];
}

export function PromptComposer({ models }: PromptComposerProps) {
  const availableModels = models.length > 0 ? models : DEFAULT_MODELS;
  const mode = useChatStore((s) => s.mode);
  const smartMode = useChatStore((s) => s.smartMode);
  const setSmartMode = useChatStore((s) => s.setSmartMode);
  const researchMode = useChatStore((s) => s.researchMode);
  const setResearchMode = useChatStore((s) => s.setResearchMode);
  const compareResearchMode = useChatStore((s) => s.compareResearchMode);
  const setCompareResearchMode = useChatStore((s) => s.setCompareResearchMode);
  const optimizeMode = useChatStore((s) => s.optimizeMode);
  const setOptimizeMode = useChatStore((s) => s.setOptimizeMode);
  const selectedModelKey = useChatStore((s) => s.selectedModelKey);
  const setSelectedModelKey = useChatStore((s) => s.setSelectedModelKey);
  const compareModelKeys = useChatStore((s) => s.compareModelKeys);
  const setCompareModelKey = useChatStore((s) => s.setCompareModelKey);
  const prompt = useChatStore((s) => s.prompt);
  const setPrompt = useChatStore((s) => s.setPrompt);
  const attachments = useChatStore((s) => s.attachments);
  const streaming = useChatStore((s) => s.streaming);

  const { submit, cancel } = useChat();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    const nextHeight = Math.min(Math.max(el.scrollHeight, 44), 160);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > 160 ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    resize();
  }, [prompt, resize]);

  useEffect(() => {
    if (availableModels.length >= 2) {
      const resolvedCompareKeys = resolveCompareModelKeys(availableModels, compareModelKeys);
      for (const index of [0, 1, 2] as const) {
        if (resolvedCompareKeys[index] !== compareModelKeys[index]) {
          setCompareModelKey(index, resolvedCompareKeys[index]);
        }
      }
      if (!selectedModelKey) {
        setSelectedModelKey(`${availableModels[0]!.provider}:${availableModels[0]!.model}`);
      }
    }
  }, [availableModels, compareModelKeys, selectedModelKey, setCompareModelKey, setSelectedModelKey]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!streaming && (prompt.trim() || attachments.length > 0)) void submit();
    }
  };

  const showModelDropdown = isModelDropdownVisible(mode, smartMode);
  const showModelRow = mode === "compare" || showModelDropdown;

  return (
    <div
      className={`${styles.card} ${
        mode === "compare" ? styles.compareCard : ""
      }`}
    >
      {showModelRow && (
        <div className={styles.modelRow}>
          {mode === "compare" ? (
            <CompareSelector
              models={availableModels}
              keys={compareModelKeys}
              onChange={setCompareModelKey}
            />
          ) : (
            <ModelSelector
              id="singleModel"
              label="Using"
              models={availableModels}
              value={selectedModelKey}
              onChange={setSelectedModelKey}
            />
          )}
        </div>
      )}

      <div className={styles.composerBody}>
        <textarea
          ref={textareaRef}
          id="promptInput"
          className={styles.textarea}
          rows={1}
          aria-label="Prompt input"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          placeholder={
            mode === "compare"
              ? "Ask once and compare model responses"
              : "Ask anything . . ."
          }
        />

        <AttachmentStrip />

        <div className={styles.featureControls}>
          <FeatureChips
            compareMode={mode === "compare"}
            smartMode={mode === "single" ? smartMode : false}
            researchMode={mode === "compare" ? compareResearchMode : researchMode}
            optimizeMode={optimizeMode}
            onSmartToggle={mode === "single" ? setSmartMode : () => undefined}
            onResearchToggle={
              mode === "compare" ? setCompareResearchMode : setResearchMode
            }
            onOptimizeToggle={setOptimizeMode}
          />
        </div>

        <div className={styles.actions}>
          <button
            className={styles.submitButton}
            type="button"
            aria-label={streaming ? "Stop" : "Send message"}
            id="submitBtn"
            onClick={() => (streaming ? cancel() : void submit())}
            disabled={!streaming && !prompt.trim() && attachments.length === 0}
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
