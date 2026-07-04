import type { ReactNode } from "react";
import type { ModelCatalogItem } from "../../types";
import {
  removeCompareModelKey,
  resolveAddedCompareModelKey,
} from "../../config/compareDefaults";
import { getModelPresentation } from "../../config/modelPresentation";
import { CortexIcon } from "../shared/CortexIcon";
import { ModelPicker } from "./ModelPicker";
import styles from "./CompareSelector.module.css";

interface CompareSelectorProps {
  models: ModelCatalogItem[];
  keys: [string, string, string];
  onChange: (index: 0 | 1 | 2, key: string) => void;
  trailingControls?: ReactNode;
}

export function CompareSelector({
  models,
  keys,
  onChange,
  trailingControls,
}: CompareSelectorProps) {
  const filledCount = keys.filter(Boolean).length;
  const visibleIndexes = ([0, 1, 2] as const).filter(
    (index) => keys[index] !== "" || index < 2,
  );
  const canRemove = filledCount > 2;
  const canAdd = filledCount < 3;

  const handleAddModel = () => {
    const emptyIndex = keys.findIndex((key) => !key) as 0 | 1 | 2;
    if (emptyIndex < 0) return;
    onChange(emptyIndex, resolveAddedCompareModelKey(models, keys));
  };

  const handleRemoveModel = (index: 0 | 1 | 2) => {
    if (!canRemove) return;
    const nextKeys = removeCompareModelKey(keys, index);
    for (const slotIndex of [0, 1, 2] as const) {
      if (nextKeys[slotIndex] !== keys[slotIndex]) {
        onChange(slotIndex, nextKeys[slotIndex]);
      }
    }
  };

  return (
    <div className={styles.wrap} aria-label="Compare model selectors">
      <div className={styles.chips}>
        {visibleIndexes.map((index, visibleIndex) => (
          <span className={styles.comparisonGroup} key={`${index}-${keys[index] || "empty"}`}>
            {visibleIndex > 0 && <CompareConnector />}
            <CompareModelSlot
              index={index}
              models={models}
              keys={keys}
              canRemove={canRemove}
              onSelect={(key) => {
                onChange(index, key);
              }}
              onRemove={() => handleRemoveModel(index)}
            />
          </span>
        ))}
      </div>

      {canAdd && (
        <button
          id="compareAddModelBtn"
          className={styles.addButton}
          type="button"
          onClick={handleAddModel}
          aria-label="Add model to comparison"
        >
          <CortexIcon name="plus" />
          <span>Add model</span>
        </button>
      )}

      {trailingControls && <div className={styles.trailingControls}>{trailingControls}</div>}
    </div>
  );
}

function CompareConnector() {
  return (
    <span
      className={styles.connector}
      data-testid="compare-connector"
      aria-hidden="true"
    >
      <CortexIcon name="swap" />
    </span>
  );
}

function CompareModelSlot({
  index,
  models,
  keys,
  canRemove,
  onSelect,
  onRemove,
}: {
  index: 0 | 1 | 2;
  models: ModelCatalogItem[];
  keys: [string, string, string];
  canRemove: boolean;
  onSelect: (key: string) => void;
  onRemove: () => void;
}) {
  const selectedKey = keys[index];
  const selectedModel = modelFromKey(selectedKey);
  const selectedMeta = getModelPresentation(selectedModel.provider, selectedModel.model);
  const activeIndexes = keys
    .map((key, slotIndex) => (key ? slotIndex : -1))
    .filter((slotIndex) => slotIndex >= 0);
  const lastActiveIndex = activeIndexes[activeIndexes.length - 1] ?? index;
  const menuAlignment =
    index === 0
      ? "left"
      : index === lastActiveIndex
        ? "right"
        : "center";

  return (
    <span id={`compareModel${index + 1}Wrap`} className={styles.chip}>
      <ModelPicker
        id={`compareModel${index + 1}`}
        models={models}
        value={selectedKey}
        onChange={onSelect}
        ariaLabel={`Compare model ${index + 1}`}
        listboxLabel={`Compare model ${index + 1} options`}
        selectedKeys={keys}
        align={menuAlignment}
        placement="up"
        className={styles.picker}
      />

      {canRemove && selectedKey && (
        <button
          type="button"
          className={styles.removeButton}
          aria-label={`Remove ${selectedMeta.label}`}
          title={`Remove ${selectedMeta.label}`}
          onClick={onRemove}
        >
          x
        </button>
      )}
    </span>
  );
}

function modelFromKey(key: string): Pick<ModelCatalogItem, "provider" | "model"> {
  const separator = key.indexOf(":");
  if (separator < 0) return { provider: "", model: key };
  return {
    provider: key.slice(0, separator),
    model: key.slice(separator + 1),
  };
}
