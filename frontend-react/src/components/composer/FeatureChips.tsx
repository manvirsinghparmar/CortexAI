import styles from "./FeatureChips.module.css";

interface FeatureChipsProps {
  smartMode: boolean;
  researchMode: boolean;
  optimizeMode: boolean;
  onSmartToggle: (v: boolean) => void;
  onResearchToggle: (v: boolean) => void;
  onOptimizeToggle: (v: boolean) => void;
}

export function FeatureChips({
  smartMode,
  researchMode,
  optimizeMode,
  onSmartToggle,
  onResearchToggle,
  onOptimizeToggle,
}: FeatureChipsProps) {
  return (
    <div className={styles.strip}>
      <Chip
        active={smartMode}
        icon="✨"
        label="Smart"
        tooltip="Gets you the best answer automatically"
        onToggle={onSmartToggle}
        aria-label="Smart routing"
      />
      <Chip
        active={researchMode}
        icon="🌐"
        label="With sources"
        tooltip="Uses latest information from the web"
        onToggle={onResearchToggle}
        aria-label="Research mode"
      />
      <Chip
        active={optimizeMode}
        icon="✎"
        label="Improve"
        tooltip="Helps you ask better for better results"
        onToggle={onOptimizeToggle}
        aria-label="Prompt optimization"
      />
    </div>
  );
}

interface ChipProps {
  active: boolean;
  icon: string;
  label: string;
  tooltip: string;
  onToggle: (v: boolean) => void;
  "aria-label": string;
}

function Chip({ active, icon, label, tooltip, onToggle, "aria-label": ariaLabel }: ChipProps) {
  return (
    <span className={styles.chipWrap}>
      <button
        type="button"
        role="switch"
        aria-checked={active}
        aria-label={ariaLabel}
        className={`${styles.chip} ${active ? styles.active : ""}`}
        onClick={() => onToggle(!active)}
      >
        <span className={styles.chipIcon} aria-hidden="true">
          {icon}
        </span>
        <span className={styles.chipLabel}>{label}</span>
      </button>
      <span className={styles.tooltip} role="tooltip">
        {tooltip}
      </span>
    </span>
  );
}
