import type { HostedBillingAction } from "../hooks/useSubscription";
import type {
  PublicBillingPlan,
  SubscriptionPlanCode,
  SubscriptionStatus,
} from "../types";

export interface PlanAction {
  label: string;
  disabled: boolean;
  kind: "primary" | "secondary";
  onClick?: () => void;
}

export function resolvePlanAction({
  plan,
  currentPlanCode,
  currentStatus,
  billingEnabled,
  canManage,
  loggedIn,
  authEnabled,
  action,
  onLogin,
  onCheckout,
  onPortal,
}: {
  plan: PublicBillingPlan;
  currentPlanCode: SubscriptionPlanCode | null;
  currentStatus?: SubscriptionStatus;
  billingEnabled: boolean;
  canManage: boolean;
  loggedIn: boolean;
  authEnabled: boolean;
  action: HostedBillingAction;
  onLogin: () => void;
  onCheckout: (planCode: SubscriptionPlanCode) => void;
  onPortal: () => void;
}): PlanAction {
  if (!billingEnabled) return { label: "Unavailable", disabled: true, kind: "secondary" };
  if (!loggedIn) {
    return {
      label: "Sign in to choose",
      disabled: !authEnabled,
      kind: plan.recommended ? "primary" : "secondary",
      onClick: authEnabled ? onLogin : undefined,
    };
  }
  if (isPaymentPastDue(currentStatus)) {
    return {
      label: "Update payment",
      disabled: action !== null || !canManage,
      kind: "primary",
      onClick: canManage ? onPortal : undefined,
    };
  }
  if (currentPlanCode === plan.code && plan.code === "free") {
    return { label: "Current plan", disabled: true, kind: "secondary" };
  }
  if (currentPlanCode && currentPlanCode !== "free") {
    if (!canManage) {
      return {
        label: currentPlanCode === plan.code ? "Current plan" : "Unavailable",
        disabled: true,
        kind: "secondary",
      };
    }
    return {
      label: currentPlanCode === plan.code ? "Manage current plan" : "Manage plan",
      disabled: action !== null,
      kind: currentPlanCode === plan.code ? "primary" : "secondary",
      onClick: onPortal,
    };
  }
  if (plan.code === "free") {
    return { label: "Current plan", disabled: true, kind: "secondary" };
  }
  return {
    label: "Upgrade",
    disabled: action !== null,
    kind: plan.recommended ? "primary" : "secondary",
    onClick: () => onCheckout(plan.code),
  };
}

export function isPaymentPastDue(status?: SubscriptionStatus): boolean {
  return status === "past_due" || status === "unpaid" || status === "incomplete";
}

export function isCancelled(status?: SubscriptionStatus): boolean {
  return status === "canceled" || status === "incomplete_expired";
}
