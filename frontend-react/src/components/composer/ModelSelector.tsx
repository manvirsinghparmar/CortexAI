import type { ModelCatalogItem } from "../../types";
import { ModelPicker } from "./ModelPicker";
import styles from "./ModelSelector.module.css";

interface ModelSelectorProps {
  models: ModelCatalogItem[];
  value: string;
  onChange: (key: string) => void;
  label?: string;
  id?: string;
}

export function ModelSelector({ models, value, onChange, label, id }: ModelSelectorProps) {
  const pickerId = id ?? "modelSelector";
  return (
    <div className={styles.wrap}>
      {label && (
        <span className={styles.label} id={`${pickerId}-label`}>
          {label}
        </span>
      )}
      <ModelPicker
        id={pickerId}
        models={models}
        value={value}
        onChange={onChange}
        ariaLabel={label ?? "Model"}
        listboxLabel={`${label ?? "Model"} options`}
        placement="up"
        align="left"
        className={styles.picker}
      />
    </div>
  );
}
