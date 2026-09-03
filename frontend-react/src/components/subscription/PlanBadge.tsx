import styles from "./PlanBadge.module.css";

export type PlanBadgeTone = "current" | "required" | "locked" | "neutral";

export function PlanBadge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: PlanBadgeTone;
}) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} data-plan-badge={tone}>
      {tone === "locked" ? <span aria-hidden="true">&#128274;</span> : null}
      <span>{label}</span>
    </span>
  );
}
