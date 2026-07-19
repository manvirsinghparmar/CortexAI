import { useEffect, useRef } from "react";
import { detailString, type SubscriptionError } from "../../subscription/subscriptionErrors";
import { PlanBadge } from "./PlanBadge";
import styles from "./UpgradeDialog.module.css";

export function UpgradeDialog({
  error,
  onClose,
  onViewPlans,
  onManageBilling,
}: {
  error: SubscriptionError | null;
  onClose: () => void;
  onViewPlans: () => void;
  onManageBilling: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const priorFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!error) return;
    priorFocusRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (focusable.length === 0) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      priorFocusRef.current?.focus();
    };
  }, [error, onClose]);

  if (!error) return null;

  const recommendedPlan = detailString(error, "recommended_plan");
  const currentPlan = detailString(error, "current_plan");
  const resetAt = detailString(error, "reset_at");
  const paymentAction = error.kind === "payment";
  const showPrimaryAction =
    paymentAction || error.kind === "access" || error.kind === "allowance";
  const title = dialogTitle(error);

  return (
    <div className={styles.backdrop} role="presentation" onMouseDown={onClose}>
      <section
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="subscription-dialog-title"
        aria-describedby="subscription-dialog-description"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button
          ref={closeRef}
          type="button"
          className={styles.close}
          aria-label="Close subscription message"
          onClick={onClose}
        >
          &times;
        </button>
        <div className={styles.icon} aria-hidden="true">
          &#128274;
        </div>
        <div className={styles.copy}>
          <div className={styles.badges}>
            {currentPlan ? <PlanBadge label={`${currentPlan} plan`} tone="current" /> : null}
            {recommendedPlan ? (
              <PlanBadge label={`${recommendedPlan} recommended`} tone="required" />
            ) : null}
          </div>
          <h2 id="subscription-dialog-title">{title}</h2>
          <p id="subscription-dialog-description">{error.message}</p>
          {resetAt && error.kind === "allowance" ? (
            <p className={styles.reset}>Allowance resets {formatDate(resetAt)}.</p>
          ) : null}
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.secondary} onClick={onClose}>
            Keep working
          </button>
          {showPrimaryAction ? (
            <button
              type="button"
              className={styles.primary}
              onClick={paymentAction ? onManageBilling : onViewPlans}
            >
              {paymentAction
                ? "Manage billing"
                : recommendedPlan
                  ? `View ${capitalize(recommendedPlan)}`
                  : "View plans"}
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function dialogTitle(error: SubscriptionError): string {
  const feature = detailString(error, "feature");
  if (error.kind === "payment") return "Your subscription needs attention";
  if (error.kind === "configuration") return "Plan access could not be verified";
  if (error.code === "model_not_in_plan") return "This model is locked on your plan";
  if (feature === "compare_model_count") return "Three-model Compare requires Pro";
  if (feature === "attachment_count") return "Too many files for this plan";
  if (feature === "attachment_size") return "This file exceeds your plan limit";
  if (feature === "research") return "Web research is unavailable";
  if (feature === "prompt_improvement") return "Improve is unavailable";
  if (feature === "file_analysis") return "File analysis is unavailable";
  if (error.kind === "allowance") return "This monthly allowance is used";
  return "This feature is unavailable on your plan";
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "at the next billing period";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}
