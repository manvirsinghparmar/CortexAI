import { useEffect, useRef, useState } from "react";
import type { ModelCatalogItem } from "../../types";
import { getModelPresentation } from "../../config/modelPresentation";
import { ProviderLogo } from "../shared/ProviderLogo";
import styles from "./ModelPicker.module.css";

export type ModelPickerPlacement = "up" | "down";
export type ModelPickerAlignment = "left" | "center" | "right";

interface ModelPickerProps {
  id: string;
  models: ModelCatalogItem[];
  value: string;
  onChange: (key: string) => void;
  ariaLabel: string;
  listboxLabel?: string;
  selectedKeys?: string[];
  disabledKeys?: string[];
  align?: ModelPickerAlignment;
  placement?: ModelPickerPlacement;
  className?: string;
  selectClassName?: string;
  buttonClassName?: string;
  menuClassName?: string;
}

export function ModelPicker({
  id,
  models,
  value,
  onChange,
  ariaLabel,
  listboxLabel = "Model options",
  selectedKeys = [],
  disabledKeys = [],
  align = "left",
  placement = "up",
  className,
  selectClassName,
  buttonClassName,
  menuClassName,
}: ModelPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const selectedModel =
    models.find((model) => modelKey(model) === value) ?? modelFromKey(value);
  const selectedMeta = getModelPresentation(
    selectedModel.provider,
    selectedModel.model,
  );
  const listboxId = `${id}Options`;
  const disabledSet = new Set(disabledKeys);
  const selectedSet = new Set(selectedKeys.filter((key) => key !== value));

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const menuPositionClass = [
    placement === "down" ? styles.menuDown : styles.menuUp,
    align === "center"
      ? styles.menuCenter
      : align === "right"
        ? styles.menuRight
        : styles.menuLeft,
    menuClassName ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span ref={rootRef} className={`${styles.root} ${className ?? ""}`}>
      <select
        id={id}
        className={`${styles.nativeSelect} ${selectClassName ?? ""}`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-hidden="true"
        tabIndex={-1}
      >
        {models.map((model) => {
          const key = modelKey(model);
          return (
            <option
              key={key}
              value={key}
              disabled={selectedSet.has(key) || disabledSet.has(key)}
            >
              {getModelPresentation(model.provider, model.model).label}
            </option>
          );
        })}
      </select>

      <button
        type="button"
        className={`${styles.button} ${buttonClassName ?? ""}`}
        aria-label={`${ariaLabel}: ${selectedMeta.label} (${selectedMeta.model})`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        title={`${selectedMeta.label}\n${selectedMeta.model}`}
        onClick={() => setIsOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setIsOpen(true);
          }
        }}
      >
        <ProviderLogo
          provider={selectedModel.provider}
          logoUrl={selectedMeta.logoUrl}
          color={selectedMeta.color}
          size={20}
        />
        <span className={styles.selectedText}>
          <strong>{selectedMeta.label}</strong>
          <small>{selectedMeta.model}</small>
        </span>
        <span className={styles.caret} aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          id={listboxId}
          className={`${styles.menu} ${menuPositionClass}`}
          role="listbox"
          aria-label={listboxLabel}
        >
          {models.map((model) => {
            const key = modelKey(model);
            const meta = getModelPresentation(model.provider, model.model);
            const isSelected = key === value;
            const isDisabled = selectedSet.has(key) || disabledSet.has(key);
            return (
              <button
                key={key}
                type="button"
                className={`${styles.option} ${isSelected ? styles.optionActive : ""}`}
                role="option"
                aria-selected={isSelected}
                aria-disabled={isDisabled}
                disabled={isDisabled}
                title={`${meta.label}\n${meta.model}`}
                onClick={() => {
                  onChange(key);
                  setIsOpen(false);
                }}
              >
                <ProviderLogo
                  provider={model.provider}
                  logoUrl={meta.logoUrl}
                  color={meta.color}
                  size={20}
                />
                <span className={styles.optionText}>
                  <strong>{meta.label}</strong>
                  <small>{meta.model}</small>
                </span>
                {isSelected && <CheckIcon />}
              </button>
            );
          })}
        </div>
      )}
    </span>
  );
}

function modelKey(model: ModelCatalogItem): string {
  return `${model.provider}:${model.model}`;
}

function modelFromKey(key: string): Pick<ModelCatalogItem, "provider" | "model"> {
  const separator = key.indexOf(":");
  if (separator < 0) return { provider: "", model: key };
  return {
    provider: key.slice(0, separator),
    model: key.slice(separator + 1),
  };
}

function CheckIcon() {
  return (
    <svg className={styles.checkIcon} viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 12 4 4 8-8" />
    </svg>
  );
}
