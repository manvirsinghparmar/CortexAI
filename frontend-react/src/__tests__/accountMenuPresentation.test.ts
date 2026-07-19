import { describe, expect, it } from "vitest";
import { getAccountMenuSubscriptionPresentation } from "../subscription/accountMenuPresentation";
import type { EntitlementsResponse, SubscriptionPlanCode, SubscriptionStatus } from "../types";

describe("account menu subscription presentation", () => {
  it("omits plan UI until backend entitlements exist", () => {
    expect(getAccountMenuSubscriptionPresentation(null)).toEqual({});
  });

  it.each([
    ["free", "free", "Free plan", "Upgrade", "/pricing", false],
    ["plus", "active", "Plus plan", "Manage plan", "/account/billing", false],
    ["plus", "past_due", "Plus plan", "Update payment", "/account/billing", true],
    ["free", "canceled", "Free plan", "View plans", "/pricing", false],
  ] as const)(
    "maps %s %s backend state to summary-only billing navigation",
    (planCode, status, planLabel, actionLabel, destination, pastDue) => {
      expect(getAccountMenuSubscriptionPresentation(entitlements(planCode, status))).toEqual({
        planLabel,
        billingActionLabel: actionLabel,
        billingPastDue: pastDue,
        billingDestination: destination,
      });
    },
  );
});

function entitlements(
  planCode: SubscriptionPlanCode,
  status: SubscriptionStatus,
): EntitlementsResponse {
  return {
    plan: {
      code: planCode,
      display_name: planCode === "free" ? "Free" : planCode === "plus" ? "Plus" : "Pro",
      status,
      source: "test",
      renews_at: "2026-08-18T00:00:00Z",
      cancel_at_period_end: false,
      grace_until: status === "past_due" ? "2026-07-21T00:00:00Z" : null,
    },
    features: {
      compare_enabled: true,
      max_compare_models: 2,
      research_enabled: true,
      prompt_improvement_enabled: true,
      file_analysis_enabled: true,
      usage_export_enabled: true,
      saved_history_enabled: true,
      models_catalog_enabled: true,
    },
    model_access: { allowed_billing_classes: ["standard"] },
    limits: { max_files_per_request: 1, max_file_bytes: 10_000_000 },
    allowances: {},
    period: {
      starts_at: "2026-07-18T00:00:00Z",
      ends_at: "2026-08-18T00:00:00Z",
    },
  };
}
