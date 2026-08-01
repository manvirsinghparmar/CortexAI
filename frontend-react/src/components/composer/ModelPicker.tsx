import {
  type CSSProperties,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import type { ModelCatalogItem } from "../../types";
import { getModelPresentation } from "../../config/modelPresentation";
import { ProviderLogo } from "../shared/ProviderLogo";
import { CortexIcon } from "../shared/CortexIcon";
import { PlanBadge } from "../subscription/PlanBadge";
import styles from "./ModelPicker.module.css";

export type ModelPickerPlacement = "up" | "down";
export type ModelPickerAlignment = "left" | "center" | "right";

const MENU_GAP = 7;
const MENU_MAX_HEIGHT = 340;
const MENU_MAX_WIDTH = 380;
const VIEWPORT_MARGIN = 20;
const EMPTY_MODELS: ModelCatalogItem[] = [];

interface ProviderGroup {
  key: string;
  label: string;
  logoUrl: string;
  color: string;
  models: ModelCatalogItem[];
}

interface ModelPickerProps {
  id: string;
  models: ModelCatalogItem[];
  value: string;
  onChange: (key: string) => void;
  ariaLabel: string;
  listboxLabel?: string;
  selectedKeys?: string[];
  disabledKeys?: string[];
  lockedKeys?: string[];
  lockedLabels?: Record<string, string>;
  onLockedSelect?: (key: string) => void;
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
  lockedKeys = [],
  lockedLabels = {},
  onLockedSelect,
  align = "left",
  placement = "up",
  className,
  selectClassName,
  buttonClassName,
  menuClassName,
}: ModelPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});
  const rootRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const providerOptionRefs = useRef(new Map<string, HTMLButtonElement>());
  const modelOptionRefs = useRef(new Map<string, HTMLButtonElement>());
  const selectedModel = models.find((model) => modelKey(model) === value) ?? modelFromKey(value);
  const selectedMeta = getModelPresentation(selectedModel.provider, selectedModel.model);
  const selectedCreditLabel =
    "credit_usage_label" in selectedModel ? selectedModel.credit_usage_label : undefined;
  const listboxId = `${id}Options`;
  const disabledSet = new Set(disabledKeys);
  const lockedSet = new Set(lockedKeys);
  const selectedSet = new Set(selectedKeys.filter((key) => key !== value));
  const providerGroups = useMemo(() => groupModelsByProvider(models), [models]);
  const activeProviderGroup = providerGroups.find((group) => group.key === activeProvider) ?? null;
  const activeModels = activeProviderGroup?.models ?? EMPTY_MODELS;

  const closeMenu = useCallback((restoreFocus = false) => {
    setIsOpen(false);
    setActiveProvider(null);
    if (restoreFocus) {
      window.requestAnimationFrame(() => buttonRef.current?.focus());
    }
  }, []);

  const updateMenuPosition = useCallback(() => {
    const button = buttonRef.current;
    if (!button) return;

    const triggerRect = button.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const width = Math.min(MENU_MAX_WIDTH, Math.max(0, viewportWidth - VIEWPORT_MARGIN * 2));
    const naturalHeight =
      menuRef.current?.scrollHeight ??
      Math.min(
        MENU_MAX_HEIGHT,
        activeProvider ? activeModels.length * 52 + 58 : providerGroups.length * 56 + 46,
      );
    const availableAbove = Math.max(0, triggerRect.top - MENU_GAP - VIEWPORT_MARGIN);
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
  }, [activeModels.length, activeProvider, align, placement, providerGroups.length]);

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

  useLayoutEffect(() => {
    if (!isOpen) return;

    if (activeProvider) {
      const preferredKey = selectedModel.provider === activeProvider ? value : "";
      const preferredOption = preferredKey ? modelOptionRefs.current.get(preferredKey) : undefined;
      const firstAvailable = activeModels
        .map((model) => modelOptionRefs.current.get(modelKey(model)))
        .find((option) => option && !option.disabled);
      (preferredOption ?? firstAvailable)?.focus();
      return;
    }

    const currentProviderOption = providerOptionRefs.current.get(selectedModel.provider);
    (currentProviderOption ?? providerOptionRefs.current.values().next().value)?.focus();
  }, [activeModels, activeProvider, isOpen, selectedModel.provider, value]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!rootRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        closeMenu();
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isOpen) {
        event.preventDefault();
        closeMenu(true);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeMenu, isOpen]);

  const menuClasses = [styles.menu, menuClassName ?? ""].filter(Boolean).join(" ");

  return (
    <span ref={rootRef} className={`${styles.root} ${className ?? ""}`}>
      <select
        id={id}
        className={`${styles.nativeSelect} ${selectClassName ?? ""}`}
        value={value}
        onChange={(event) => {
          const nextKey = event.target.value;
          if (lockedSet.has(nextKey)) {
            onLockedSelect?.(nextKey);
            return;
          }
          onChange(nextKey);
        }}
        aria-hidden="true"
        tabIndex={-1}
      >
        {models.map((model) => {
          const key = modelKey(model);
          return (
            <option
              key={key}
              value={key}
              disabled={selectedSet.has(key) || disabledSet.has(key) || lockedSet.has(key)}
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
        aria-label={`${ariaLabel}: ${selectedMeta.label} (${selectedMeta.model})${
          selectedCreditLabel ? `, ${selectedCreditLabel} credit use` : ""
        }`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        title={`${selectedMeta.label}\n${selectedMeta.model}${
          selectedCreditLabel ? `\n${selectedCreditLabel} credit use` : ""
        }`}
        onClick={() => {
          if (isOpen) {
            closeMenu();
            return;
          }
          setActiveProvider(null);
          setIsOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActiveProvider(null);
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
        {lockedSet.has(value) ? (
          <span className={styles.selectedLock} aria-label="Locked on current plan">
            &#128274;
          </span>
        ) : null}
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
            data-picker-view={activeProvider ? "models" : "providers"}
            onKeyDown={(event) => {
              if (activeProvider && event.key === "ArrowLeft") {
                event.preventDefault();
                setActiveProvider(null);
                return;
              }
              if (
                event.key !== "ArrowDown" &&
                event.key !== "ArrowUp" &&
                event.key !== "Home" &&
                event.key !== "End"
              ) {
                return;
              }

              const options = Array.from(
                menuRef.current?.querySelectorAll<HTMLButtonElement>(
                  'button[role="option"]:not(:disabled)',
                ) ?? [],
              );
              if (options.length === 0) return;
              event.preventDefault();
              const currentIndex = options.indexOf(document.activeElement as HTMLButtonElement);
              const nextIndex =
                currentIndex < 0
                  ? event.key === "ArrowUp" || event.key === "End"
                    ? options.length - 1
                    : 0
                  : event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? options.length - 1
                      : event.key === "ArrowDown"
                        ? (currentIndex + 1) % options.length
                        : (currentIndex - 1 + options.length) % options.length;
              options[nextIndex]?.focus();
            }}
          >
            {activeProviderGroup ? (
              <>
                <button
                  type="button"
                  className={styles.backOption}
                  role="option"
                  aria-selected="false"
                  aria-label="Back to providers"
                  onClick={() => setActiveProvider(null)}
                >
                  <CortexIcon name="chevron-left" />
                  <span className={styles.backText}>
                    <small>Providers</small>
                    <strong>{activeProviderGroup.label} models</strong>
                  </span>
                </button>
                {activeModels.map((model) => {
                  const key = modelKey(model);
                  const meta = getModelPresentation(model.provider, model.model);
                  const isSelected = key === value;
                  const isDisabled = selectedSet.has(key) || disabledSet.has(key);
                  const isLocked = lockedSet.has(key);
                  return (
                    <button
                      ref={(node) => {
                        if (node) modelOptionRefs.current.set(key, node);
                        else modelOptionRefs.current.delete(key);
                      }}
                      key={key}
                      type="button"
                      className={`${styles.option} ${
                        isSelected ? styles.optionActive : ""
                      } ${isLocked ? styles.optionLocked : ""}`}
                      role="option"
                      aria-selected={isSelected}
                      aria-disabled={isDisabled || isLocked}
                      data-model-key={key}
                      disabled={isDisabled}
                      title={`${meta.label}\n${meta.model}`}
                      onClick={() => {
                        if (isLocked) {
                          onLockedSelect?.(key);
                          closeMenu();
                          return;
                        }
                        onChange(key);
                        closeMenu();
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
                        <small>
                          {meta.model}
                          {model.credit_usage_label
                            ? ` \u00b7 ${model.credit_usage_label} credit use`
                            : ""}
                        </small>
                      </span>
                      {isSelected && <CortexIcon name="check" className={styles.checkIcon} />}
                      {isLocked ? (
                        <PlanBadge label={lockedLabels[key] ?? "Upgrade"} tone="locked" />
                      ) : null}
                    </button>
                  );
                })}
              </>
            ) : (
              <>
                <div className={styles.menuHeader} role="presentation">
                  <strong>Choose a provider</strong>
                  <span>
                    {providerGroups.length} provider
                    {providerGroups.length === 1 ? "" : "s"}
                  </span>
                </div>
                {providerGroups.map((group) => {
                  const isCurrentProvider = group.key === selectedModel.provider;
                  return (
                    <button
                      ref={(node) => {
                        if (node) providerOptionRefs.current.set(group.key, node);
                        else providerOptionRefs.current.delete(group.key);
                      }}
                      key={group.key}
                      type="button"
                      className={`${styles.option} ${styles.providerOption} ${
                        isCurrentProvider ? styles.providerOptionCurrent : ""
                      }`}
                      role="option"
                      aria-selected={isCurrentProvider}
                      data-provider-key={group.key}
                      aria-label={`${group.label}, ${group.models.length} ${
                        group.models.length === 1 ? "model" : "models"
                      }${
                        isCurrentProvider
                          ? `, current provider, selected ${selectedMeta.label}`
                          : ""
                      }`}
                      title={`View ${group.label} models`}
                      onClick={() => setActiveProvider(group.key)}
                    >
                      <ProviderLogo
                        provider={group.key}
                        logoUrl={group.logoUrl}
                        color={group.color}
                        size={20}
                      />
                      <span className={styles.optionText}>
                        <strong>{group.label}</strong>
                        <small>
                          {group.models.length} {group.models.length === 1 ? "model" : "models"}
                          {isCurrentProvider ? ` \u00b7 ${selectedMeta.label} selected` : ""}
                        </small>
                      </span>
                      <span className={styles.providerActions} aria-hidden="true">
                        {isCurrentProvider ? (
                          <CortexIcon name="check" className={styles.checkIcon} />
                        ) : null}
                        <CortexIcon name="chevron-right" className={styles.providerChevron} />
                      </span>
                    </button>
                  );
                })}
              </>
            )}
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

function groupModelsByProvider(models: ModelCatalogItem[]): ProviderGroup[] {
  const groups = new Map<string, ProviderGroup>();
  for (const model of models) {
    const existing = groups.get(model.provider);
    if (existing) {
      existing.models.push(model);
      continue;
    }

    const meta = getModelPresentation(model.provider, model.model);
    groups.set(model.provider, {
      key: model.provider,
      label: meta.providerLabel,
      logoUrl: meta.logoUrl,
      color: meta.color,
      models: [model],
    });
  }
  return Array.from(groups.values());
}
