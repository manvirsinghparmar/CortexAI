import type { EntitlementsResponse } from "../types";

export interface AccountMenuSubscriptionPresentation {
  planLabel?: string;
  billingActionLabel?: string;
  billingPastDue?: boolean;
  billingDestination?: "/pricing" | "/account/billing";
}

export function getAccountMenuSubscriptionPresentation(
  entitlements: EntitlementsResponse | null,
): AccountMenuSubscriptionPresentation {
  const plan = entitlements?.plan;
  if (!plan) return {};

  const billingPastDue = ["past_due", "unpaid", "incomplete"].includes(plan.status);
  const cancelled = ["canceled", "incomplete_expired"].includes(plan.status);
  return {
    planLabel: `${plan.display_name} plan`,
    billingActionLabel: billingPastDue
      ? "Update payment"
      : cancelled
        ? "View plans"
        : plan.code === "free"
          ? "Upgrade"
          : "Manage plan",
    billingPastDue,
    billingDestination:
      billingPastDue || (plan.code !== "free" && !cancelled) ? "/account/billing" : "/pricing",
  };
}
