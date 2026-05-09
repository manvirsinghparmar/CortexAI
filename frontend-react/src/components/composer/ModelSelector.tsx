import type { ModelCatalogItem } from "../../types";
import styles from "./ModelSelector.module.css";

interface ModelSelectorProps {
  models: ModelCatalogItem[];
  value: string;
  onChange: (key: string) => void;
  label?: string;
  id?: string;
}

export function ModelSelector({ models, value, onChange, label, id }: ModelSelectorProps) {
  const grouped = groupByProvider(models);

  return (
    <div className={styles.wrap}>
      {label && (
        <span className={styles.label} id={id ? `${id}-label` : undefined}>
          {label}
        </span>
      )}
      <select
        id={id}
        className={styles.select}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
      >
        {Object.entries(grouped).map(([provider, items]) => (
          <optgroup key={provider} label={provider.charAt(0).toUpperCase() + provider.slice(1)}>
            {items.map((m) => (
              <option key={`${m.provider}:${m.model}`} value={`${m.provider}:${m.model}`}>
                {m.model}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

function groupByProvider(models: ModelCatalogItem[]): Record<string, ModelCatalogItem[]> {
  return models.reduce<Record<string, ModelCatalogItem[]>>((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = [];
    acc[m.provider]!.push(m);
    return acc;
  }, {});
}
