import type { ChatMode } from "../../types";
import styles from "./ModeToggle.module.css";

interface ModeToggleProps {
  mode: ChatMode;
  onChange: (mode: ChatMode) => void;
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className={styles.toggle} role="tablist" aria-label="Chat mode">
      <button
        className={`${styles.btn} ${mode === "single" ? styles.active : ""}`}
        role="tab"
        aria-selected={mode === "single"}
        onClick={() => onChange("single")}
      >
        Ask
      </button>
      <button
        className={`${styles.btn} ${mode === "compare" ? styles.active : ""}`}
        role="tab"
        aria-selected={mode === "compare"}
        onClick={() => onChange("compare")}
      >
        Compare
      </button>
    </div>
  );
}
