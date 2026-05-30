import type { ModelCatalogItem } from "../../types";
import styles from "./CompareSelector.module.css";

interface CompareSelectorProps {
  models: ModelCatalogItem[];
  keys: [string, string, string];
  onChange: (index: 0 | 1 | 2, key: string) => void;
}

export function CompareSelector({ models, keys, onChange }: CompareSelectorProps) {
  const filledCount = keys.filter(Boolean).length;
  const canRemove = filledCount > 2;
  const canAdd = filledCount < 3 && !keys.includes("");

  const handleAddModel = () => {
    const emptyIndex = keys.findIndex((key) => !key) as 0 | 1 | 2;
    if (emptyIndex < 0) return;
    // Set to empty string so a "Select model…" placeholder appears
    onChange(emptyIndex, "");
  };

  return (
    <div className={styles.wrap} aria-label="Compare model selectors">
      <div className={styles.chips}>
        {([0, 1, 2] as const)
          .filter((i) => keys[i] !== "" || (i === 2 && keys[0] && keys[1] && !keys[2] && !canAdd))
          .map((i) => (
            <span key={i} className={styles.chip}>
              <select
                value={keys[i]}
                onChange={(e) => onChange(i, e.target.value)}
                aria-label={`Compare model ${i + 1}`}
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
        <button
          className={styles.addButton}
          type="button"
          onClick={handleAddModel}
          aria-label="Add model to comparison"
        >
          <Icon />
          <span>Add Model</span>
        </button>
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

function Icon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}
