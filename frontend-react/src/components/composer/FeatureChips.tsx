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
      <Chip active={smartMode} label="Smart" onToggle={onSmartToggle} ariaLabel="Smart routing" />
      <Chip active={researchMode} label="With Sources" onToggle={onResearchToggle} ariaLabel="Research mode" />
      <Chip
        active={optimizeMode}
        label="Improve"
        onToggle={onOptimizeToggle}
        ariaLabel="Prompt optimization"
      />
    </div>
  );
}

interface ChipProps {
  active: boolean;
  label: string;
  onToggle: (v: boolean) => void;
  ariaLabel: string;
}

function Chip({ active, label, onToggle, ariaLabel }: ChipProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      aria-label={ariaLabel}
      className={`${styles.chip} ${active ? styles.active : ""}`}
      onClick={() => onToggle(!active)}
    >
      {label}
    </button>
  );
}
