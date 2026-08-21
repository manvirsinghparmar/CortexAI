import type { WorkRunStatus, WorkSessionStatus } from "../../types";
import styles from "./Work.module.css";

const LABELS: Record<string, string> = {
  created: "Planning",
  planning: "Planning",
  running: "Working",
  waiting_for_approval: "Needs approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Stopped",
  budget_exhausted: "Budget reached",
  idle: "Ready",
};

export function WorkStatusPill({
  status,
}: {
  status: WorkRunStatus | WorkSessionStatus | "idle";
}) {
  return (
    <span
      className={`${styles.statusPill} ${styles[`status_${status}`] || ""}`}
      aria-live="polite"
    >
      <span className={styles.statusDot} aria-hidden="true" />
      {LABELS[status] || status.replaceAll("_", " ")}
    </span>
  );
}
