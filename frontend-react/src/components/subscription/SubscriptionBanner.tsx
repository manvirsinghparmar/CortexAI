import type { EntitlementsResponse } from "../../types";
import { PlanBadge } from "./PlanBadge";
import styles from "./SubscriptionBanner.module.css";

export function SubscriptionBanner({
  entitlements,
  onManageBilling,
}: {
  entitlements: EntitlementsResponse | null;
  onManageBilling?: () => void;
}) {
  if (!entitlements) return null;

  const status = entitlements.plan.status;
  const paymentIssue = status === "past_due" || status === "unpaid";
  const cancellationPending = entitlements.plan.cancel_at_period_end;
  if (!paymentIssue && !cancellationPending) return null;

  const message = paymentIssue
    ? entitlements.plan.grace_until
      ? `Update your payment method before ${formatDate(entitlements.plan.grace_until)} to keep paid access.`
      : "Update your payment method to restore paid-plan access."
    : `Your ${entitlements.plan.display_name} plan ends ${formatDate(entitlements.plan.renews_at)}.`;

  return (
    <section
      className={`${styles.banner} ${paymentIssue ? styles.warning : styles.notice}`}
      role={paymentIssue ? "alert" : "status"}
      aria-label="Subscription status"
    >
      <PlanBadge
        label={paymentIssue ? "Payment issue" : "Cancellation scheduled"}
        tone={paymentIssue ? "locked" : "neutral"}
      />
      <p>{message}</p>
      {onManageBilling ? (
        <button type="button" onClick={onManageBilling}>
          Manage billing
        </button>
      ) : null}
    </section>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "at period end";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}
