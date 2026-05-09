import { ModelSelector } from "./ModelSelector";
import type { ModelCatalogItem } from "../../types";
import styles from "./CompareSelector.module.css";

interface CompareSelectorProps {
  models: ModelCatalogItem[];
  keys: [string, string, string];
  onChange: (index: 0 | 1 | 2, key: string) => void;
}

export function CompareSelector({ models, keys, onChange }: CompareSelectorProps) {
  const activeCount = keys.filter(Boolean).length;
  const showThird = activeCount >= 2 && (keys[2] !== "" || activeCount < 3);

  const handleRemove = (index: 0 | 1 | 2) => {
    onChange(index, "");
  };

  const handleAddModel = () => {
    if (!keys[2]) onChange(2, models[0] ? `${models[0].provider}:${models[0].model}` : "");
  };

  return (
    <div className={styles.wrap} aria-label="Compare model selectors">
      <span className={styles.label}>Compare:</span>

      {([0, 1] as const).map((i) => (
        <span key={i} className={styles.slot}>
          <ModelSelector
            id={`compareModel${i + 1}`}
            models={models}
            value={keys[i]}
            onChange={(v) => onChange(i, v)}
          />
          {activeCount > 2 && (
            <button
              className={styles.removeBtn}
              type="button"
              aria-label={`Remove model ${i + 1} from comparison`}
              onClick={() => handleRemove(i)}
            >
              &times;
            </button>
          )}
          {i === 0 && <span className={styles.sep}>vs</span>}
        </span>
      ))}

      {showThird && (
        <span className={styles.slot}>
          <span className={styles.sep}>vs</span>
          <ModelSelector
            id="compareModel3"
            models={models}
            value={keys[2]}
            onChange={(v) => onChange(2, v)}
          />
          <button
            className={styles.removeBtn}
            type="button"
            aria-label="Remove model 3 from comparison"
            onClick={() => handleRemove(2)}
          >
            &times;
          </button>
        </span>
      )}

      {!showThird && activeCount <= 2 && (
        <button
          className={styles.addBtn}
          type="button"
          onClick={handleAddModel}
          aria-label="Add a third model"
        >
          + Add Model
        </button>
      )}
    </div>
  );
}
