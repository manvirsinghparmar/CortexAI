import styles from "./FeatureChips.module.css";

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
  return (
    <div className={styles.strip}>
      {!compareMode && (
        <Chip
          id="routeSmartBtn"
          active={smartMode}
          label="Smart"
          onToggle={onSmartToggle}
          ariaLabel="Smart routing"
        />
      )}
      <Chip
        id="routeResearchBtn"
        active={researchMode}
        label={compareMode ? "With sources" : "Web"}
        onToggle={onResearchToggle}
        ariaLabel={compareMode ? "Compare with sources" : "Research mode"}
      />
      <Chip
        id="routeOptimizeBtn"
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
  id?: string;
}

function Chip({ active, label, onToggle, ariaLabel, id }: ChipProps) {
  return (
    <button
      id={id}
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
