import type { ModelCatalogItem } from "../../types";
import styles from "./CompareSelector.module.css";

interface CompareSelectorProps {
  models: ModelCatalogItem[];
  keys: [string, string, string];
  onChange: (index: 0 | 1 | 2, key: string) => void;
}

export function CompareSelector({ models, keys, onChange }: CompareSelectorProps) {
  const activeIndexes = keys
    .map((key, index) => ({ key, index: index as 0 | 1 | 2 }))
    .filter((item) => item.key);
  const canRemove = activeIndexes.length > 2;
  const canAdd = activeIndexes.length < 3;

  const handleAddModel = () => {
    const emptyIndex = keys.findIndex((key) => !key) as 0 | 1 | 2;
    if (emptyIndex < 0) return;
    const next = models.find((model) => !keys.includes(modelKey(model)));
    onChange(emptyIndex, next ? modelKey(next) : modelKey(models[0]));
  };

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
              {models.map((model) => (
                <option key={modelKey(model)} value={modelKey(model)}>
                  {model.model}
                </option>
              ))}
            </select>
            {canRemove && (
              <button
                type="button"
                aria-label={`Remove ${modelName(key)}`}
                onClick={() => onChange(index, "")}
              >
                x
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
