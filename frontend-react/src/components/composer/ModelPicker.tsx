import {
  type CSSProperties,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { ModelCatalogItem } from "../../types";
import { getModelPresentation } from "../../config/modelPresentation";
import { ProviderLogo } from "../shared/ProviderLogo";
import styles from "./ModelPicker.module.css";

export type ModelPickerPlacement = "up" | "down";
export type ModelPickerAlignment = "left" | "center" | "right";

const MENU_GAP = 7;
const MENU_MAX_HEIGHT = 300;
const MENU_MAX_WIDTH = 380;
const VIEWPORT_MARGIN = 20;

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
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});
  const rootRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const selectedModel =
    models.find((model) => modelKey(model) === value) ?? modelFromKey(value);
  const selectedMeta = getModelPresentation(
    selectedModel.provider,
    selectedModel.model,
  );
  const listboxId = `${id}Options`;
  const disabledSet = new Set(disabledKeys);
  const selectedSet = new Set(selectedKeys.filter((key) => key !== value));

  const updateMenuPosition = useCallback(() => {
    const button = buttonRef.current;
    if (!button) return;

    const triggerRect = button.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(
      MENU_MAX_WIDTH,
      Math.max(0, viewportWidth - VIEWPORT_MARGIN * 2),
    );
    const naturalHeight =
      menuRef.current?.scrollHeight ??
      Math.min(MENU_MAX_HEIGHT, models.length * 52 + 12);
    const availableAbove = Math.max(
      0,
      triggerRect.top - MENU_GAP - VIEWPORT_MARGIN,
    );
    const availableBelow = Math.max(
      0,
      viewportHeight - triggerRect.bottom - MENU_GAP - VIEWPORT_MARGIN,
    );
    const prefersUp = placement === "up";
    const openUp = prefersUp
      ? availableAbove >= Math.min(naturalHeight, MENU_MAX_HEIGHT) ||
        availableAbove >= availableBelow
      : !(
          availableBelow >= Math.min(naturalHeight, MENU_MAX_HEIGHT) ||
          availableBelow >= availableAbove
        );
    const availableHeight = openUp ? availableAbove : availableBelow;
    const maxHeight = Math.min(MENU_MAX_HEIGHT, availableHeight);
    const renderedHeight = Math.min(naturalHeight, maxHeight);

    let left =
      align === "right"
        ? triggerRect.right - width
        : align === "center"
          ? triggerRect.left + triggerRect.width / 2 - width / 2
          : triggerRect.left;
    left = Math.min(
      Math.max(VIEWPORT_MARGIN, left),
      Math.max(VIEWPORT_MARGIN, viewportWidth - width - VIEWPORT_MARGIN),
    );

    const top = openUp
      ? triggerRect.top - MENU_GAP - renderedHeight
      : triggerRect.bottom + MENU_GAP;

    setMenuStyle({
      top: Math.max(VIEWPORT_MARGIN, top),
      left,
      width,
      maxHeight,
    });
  }, [align, models.length, placement]);

  useLayoutEffect(() => {
    if (!isOpen) return;

    updateMenuPosition();
    const frame = window.requestAnimationFrame(updateMenuPosition);
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [isOpen, updateMenuPosition]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !rootRef.current?.contains(target) &&
        !menuRef.current?.contains(target)
      ) {
        setIsOpen(false);
      }
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

  const menuClasses = [styles.menu, menuClassName ?? ""]
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
        ref={buttonRef}
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

      {isOpen &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={menuRef}
            id={listboxId}
            className={menuClasses}
            style={menuStyle}
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
          </div>,
          document.body,
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
