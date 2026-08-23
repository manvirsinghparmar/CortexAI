import type { PublicBillingPlan, SubscriptionPlanCode } from "../types";

export function planFeatures(plan: PublicBillingPlan): string[] {
  const allowances = plan.allowances;
  const classes = plan.features.allowed_billing_classes;
  return [
    `${formatCount(allowances.ai_credits)} AI credits per month`,
    `Compare up to ${plan.features.max_compare_models} models`,
    "Advanced Web Search draws from AI credits",
    "Improve Prompt draws from AI credits",
    "File upload is free; model processing uses AI credits",
    classes.includes("premium")
      ? "Premium model access"
      : classes.includes("advanced")
        ? "Advanced model access"
        : "Economical and selected standard models",
  ];
}

export function planSummary(code: SubscriptionPlanCode): string {
  if (code === "plus") return "For regular research and creation";
  if (code === "pro") return "For high-volume and premium-model work";
  return "For trying CortexAI and occasional work";
}

export function formatPrice(value: number): string {
  return value === 0 ? "$0" : `$${value.toFixed(2)}`;
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}
