import { ModelSelector } from "./ModelSelector";
import type { ModelCatalogItem } from "../../types";

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
    <div className="flex items-center gap-2 flex-wrap" aria-label="Compare model selectors">
      <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0">Compare:</span>

      {([0, 1] as const).map((i) => (
        <span key={i} className="flex items-center gap-1">
          <ModelSelector
            id={`compareModel${i + 1}`}
            models={models}
            value={keys[i]}
            onChange={(v) => onChange(i, v)}
          />
          {activeCount > 2 && (
            <button
              className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors px-1"
              type="button"
              aria-label={`Remove model ${i + 1} from comparison`}
              onClick={() => handleRemove(i)}
            >
              ×
            </button>
          )}
          {i === 0 && <span className="text-xs text-zinc-300 dark:text-zinc-600">vs</span>}
        </span>
      ))}

      {showThird && (
        <span className="flex items-center gap-1">
          <span className="text-xs text-zinc-300 dark:text-zinc-600">vs</span>
          <ModelSelector
            id="compareModel3"
            models={models}
            value={keys[2]}
            onChange={(v) => onChange(2, v)}
          />
          <button
            className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors px-1"
            type="button"
            aria-label="Remove model 3 from comparison"
            onClick={() => handleRemove(2)}
          >
            ×
          </button>
        </span>
      )}

      {!showThird && activeCount <= 2 && (
        <button
          className="text-xs px-2.5 py-1 rounded-full border border-dashed border-zinc-300 dark:border-zinc-600 text-zinc-400 dark:text-zinc-500 hover:border-zinc-500 dark:hover:border-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
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
