import { useMemo, useState } from "react";
import type { ModelCatalogItem } from "../../types";
import styles from "./CompareSelector.module.css";

interface CompareSelectorProps {
  models: ModelCatalogItem[];
  keys: [string, string, string];
  onChange: (index: 0 | 1 | 2, key: string) => void;
}

export function CompareSelector({ models, keys, onChange }: CompareSelectorProps) {
  const [adding, setAdding] = useState(false);
  const activeIndexes = keys
    .map((key, index) => ({ key, index: index as 0 | 1 | 2 }))
    .filter((item) => item.key);
  const activeKeys = activeIndexes.map((item) => item.key);
  const canRemove = activeIndexes.length > 2;
  const canAdd = activeIndexes.length < 3;
  const addCandidates = useMemo(
    () => models.filter((model) => !activeKeys.includes(modelKey(model))),
    [models, activeKeys],
  );

  const handleAddModel = (key: string) => {
    const emptyIndex = keys.findIndex((item) => !item);
    if (emptyIndex < 0) return;
    onChange(emptyIndex as 0 | 1 | 2, key);
    setAdding(false);
  };

  const optionModelsFor = (currentKey: string) =>
    models.filter((model) => {
      const key = modelKey(model);
      return key === currentKey || !activeKeys.includes(key);
    });

  return (
    <div className={styles.wrap} aria-label="Compare model selectors">
      <div className={styles.chips}>
        {activeIndexes.map(({ key, index }) => (
          <span key={index} className={styles.chip}>
            <select
              value={key}
              onChange={(event) => onChange(index, event.target.value)}
              aria-label={`Compare model ${index + 1}`}
            >
              {optionModelsFor(key).map((model) => (
                <option key={modelKey(model)} value={modelKey(model)}>
                  {modelLabel(model)}
                </option>
              ))}
            </select>
            {canRemove && (
              <button
                type="button"
                aria-label={`Remove ${modelName(key)}`}
                onClick={() => onChange(index, "")}
              >
                {keys[i] === "" && (
                  <option value="" disabled>
                    Select model…
                  </option>
                )}
                {models.map((model) => (
                  <option key={modelKey(model)} value={modelKey(model)}>
                    {model.model}
                  </option>
                ))}
              </select>
              {canRemove && keys[i] !== "" && (
                <button
                  type="button"
                  aria-label={`Remove ${modelName(keys[i])}`}
                  onClick={() => onChange(i, "")}
                >
                  ×
                </button>
              )}
              {keys[i] === "" && (
                <button
                  type="button"
                  aria-label="Cancel adding model"
                  onClick={() => onChange(i, "")}
                >
                  ×
                </button>
              )}
            </span>
          ))}
      </div>

      {canAdd && (
        <div className={styles.addWrap}>
          <button
            className={styles.addButton}
            type="button"
            onClick={() => setAdding((value) => !value)}
            aria-expanded={adding}
            aria-haspopup="menu"
            aria-label="Choose a model to add"
          >
            <Icon />
            <span>Add Model</span>
          </button>

          {adding && (
            <div className={styles.addMenu} role="menu" aria-label="Available compare models">
              {addCandidates.length > 0 ? (
                addCandidates.map((model) => {
                  const key = modelKey(model);
                  return (
                    <button
                      key={key}
                      type="button"
                      role="menuitem"
                      onClick={() => handleAddModel(key)}
                    >
                      <span>{modelLabel(model)}</span>
                      <small>{providerLabel(model.provider)}</small>
                    </button>
                  );
                })
              ) : (
                <span className={styles.emptyAdd}>All models added</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function modelKey(model?: ModelCatalogItem) {
  return model ? `${model.provider}:${model.model}` : "";
}

function modelName(key: string) {
  return key.split(":").slice(1).join(":") || key;
}

function modelLabel(model: ModelCatalogItem) {
  const known: Record<string, string> = {
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "deepseek-chat": "DeepSeek Chat",
    "deepseek-reasoner": "DeepSeek Reasoner",
    "grok-4-1-fast-non-reasoning": "Grok 4.1 Fast",
    "grok-4-1-fast-reasoning": "Grok 4.1 Reasoning",
    "claude-sonnet-4-5": "Claude Sonnet 4.5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-opus-4-5": "Claude Opus 4.5",
    "claude-opus-4-6": "Claude Opus 4.6",
  };
  return known[model.model] ?? model.model;
}

function providerLabel(provider: string) {
  const known: Record<string, string> = {
    openai: "OpenAI",
    gemini: "Gemini",
    deepseek: "DeepSeek",
    grok: "Grok",
    claude: "Claude",
  };
  return known[provider] ?? provider;
}

function Icon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}
