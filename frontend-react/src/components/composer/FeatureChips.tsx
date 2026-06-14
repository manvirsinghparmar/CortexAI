import { useEffect, useRef, useState } from "react";
import styles from "./FeatureChips.module.css";

const TOUCH_TOOLTIP_DURATION_MS = 2000;

interface FeatureChipsProps {
  smartMode: boolean;
  researchMode: boolean;
  optimizeMode: boolean;
  compareMode?: boolean;
  onSmartToggle: (v: boolean) => void;
  onResearchToggle: (v: boolean) => void;
  onOptimizeToggle: (v: boolean) => void;
}

export function FeatureChips({
  smartMode,
  researchMode,
  optimizeMode,
  compareMode = false,
  onSmartToggle,
  onResearchToggle,
  onOptimizeToggle,
}: FeatureChipsProps) {
  const [touchTooltipId, setTouchTooltipId] = useState<string | null>(null);
  const touchTooltipTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (touchTooltipTimer.current !== null) {
        window.clearTimeout(touchTooltipTimer.current);
      }
    };
  }, []);

  const showTouchTooltip = (tooltipId: string) => {
    if (touchTooltipTimer.current !== null) {
      window.clearTimeout(touchTooltipTimer.current);
    }
    setTouchTooltipId(tooltipId);
    touchTooltipTimer.current = window.setTimeout(() => {
      setTouchTooltipId(null);
      touchTooltipTimer.current = null;
    }, TOUCH_TOOLTIP_DURATION_MS);
  };

  return (
    <div className={styles.strip}>
      {!compareMode && (
        <Chip
          id="routeSmartBtn"
          active={smartMode}
          label="Smart"
          tooltip="Gets you the best answer automatically"
          tooltipAlign="start"
          onToggle={onSmartToggle}
          ariaLabel="Smart routing"
          touchTooltipId={touchTooltipId}
          onTouchTooltip={showTouchTooltip}
        />
      )}
      <Chip
        id="routeResearchBtn"
        active={researchMode}
        label={compareMode ? "With sources" : "Web"}
        tooltip="Uses latest information from the web"
        tooltipAlign={compareMode ? "start" : "center"}
        onToggle={onResearchToggle}
        ariaLabel={compareMode ? "Compare with sources" : "Research mode"}
        touchTooltipId={touchTooltipId}
        onTouchTooltip={showTouchTooltip}
      />
      <Chip
        id="routeOptimizeBtn"
        active={optimizeMode}
        label="Improve"
        tooltip="Helps you ask better for better results"
        tooltipAlign="end"
        onToggle={onOptimizeToggle}
        ariaLabel="Prompt optimization"
        touchTooltipId={touchTooltipId}
        onTouchTooltip={showTouchTooltip}
      />
    </div>
  );
}

interface ChipProps {
  active: boolean;
  label: string;
  onToggle: (v: boolean) => void;
  ariaLabel: string;
  tooltip: string;
  tooltipAlign: "start" | "center" | "end";
  touchTooltipId: string | null;
  onTouchTooltip: (tooltipId: string) => void;
  id?: string;
}

function Chip({
  active,
  label,
  tooltip,
  tooltipAlign,
  onToggle,
  ariaLabel,
  touchTooltipId,
  onTouchTooltip,
  id,
}: ChipProps) {
  const tooltipId = `${id ?? label.toLowerCase().replace(/\s+/g, "-")}-tooltip`;
  const touchVisible = touchTooltipId === tooltipId;

  return (
    <span className={styles.chipWrap}>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={active}
        aria-label={ariaLabel}
        aria-describedby={tooltipId}
        className={`${styles.chip} ${active ? styles.active : ""}`}
        onPointerUp={(event) => {
          if (event.pointerType === "touch") {
            onTouchTooltip(tooltipId);
          }
        }}
        onClick={() => onToggle(!active)}
      >
        {label}
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        data-touch-visible={touchVisible ? "true" : "false"}
        className={`${styles.tooltip} ${styles[`tooltip${capitalize(tooltipAlign)}`]} ${
          touchVisible ? styles.tooltipVisible : ""
        }`}
      >
        {tooltip}
      </span>
    </span>
  );
}

function capitalize(value: string) {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}
