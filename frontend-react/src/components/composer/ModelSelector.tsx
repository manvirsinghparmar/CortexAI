import type { ModelCatalogItem } from "../../types";

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
    <div className="flex items-center gap-1.5">
      {label && (
        <span className="text-xs text-zinc-400 dark:text-zinc-500 shrink-0" id={id ? `${id}-label` : undefined}>
          {label}
        </span>
      )}
      <select
        id={id}
        className="text-xs bg-zinc-100 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 rounded-md px-2 py-1 border-none focus:ring-1 focus:ring-zinc-400 dark:focus:ring-zinc-500 cursor-pointer"
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
