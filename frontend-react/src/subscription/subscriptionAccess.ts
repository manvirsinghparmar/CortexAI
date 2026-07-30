import type {
  BillingPlansResponse,
  EntitlementsResponse,
  ModelBillingClass,
  ModelCatalogItem,
  SubscriptionMeterKey,
  SubscriptionPlanCode,
} from "../types";
import {
  localSubscriptionDenial,
  SubscriptionError,
} from "./subscriptionErrors";

type FeatureKey =
  | "compare"
  | "compare_model_count"
  | "research"
  | "prompt_improvement"
  | "file_analysis"
  | "attachment_count"
  | "attachment_size";

const METER_LABELS: Record<SubscriptionMeterKey, string> = {
  ai_credits: "AI credit",
};

export function modelAccessError(
  model: ModelCatalogItem | undefined,
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionError | null {
  if (!entitlements) return null;
  if (!model || !isBillingClass(model.billing_class)) {
    return configurationError("The selected model's plan access could not be verified safely.");
  }
  if (entitlements.model_access.allowed_billing_classes.includes(model.billing_class)) {
    return null;
  }

  const recommended = recommendedPlan(
    plans,
    entitlements.plan.code,
    (plan) => plan.features.allowed_billing_classes.includes(model.billing_class),
  );
  return localSubscriptionDenial({
    code: "model_not_in_plan",
    message: `${model.model} is not available on the ${entitlements.plan.display_name} plan.`,
    details: {
      model: model.model,
      billing_class: model.billing_class,
      current_plan: entitlements.plan.code,
      recommended_plan: recommended,
      reset_at: entitlements.period.ends_at,
    },
  });
}

export function compareTargetAccessError(
  targetCount: number,
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionError | null {
  if (!entitlements || targetCount <= entitlements.features.max_compare_models) return null;
  const recommended = recommendedPlan(
    plans,
    entitlements.plan.code,
    (plan) => plan.features.max_compare_models >= targetCount,
  );
  return featureError(
    "compare_model_count",
    `The ${entitlements.plan.display_name} plan supports up to ${entitlements.features.max_compare_models} Compare models.`,
    entitlements,
    recommended,
  );
}

export function featureAccessError(
  feature: "research" | "prompt_improvement" | "file_analysis",
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionError | null {
  if (!entitlements) return null;
  const enabled =
    feature === "research"
      ? entitlements.features.research_enabled
      : feature === "prompt_improvement"
        ? entitlements.features.prompt_improvement_enabled
        : entitlements.features.file_analysis_enabled;
  if (enabled) return null;

  const recommended = recommendedPlan(plans, entitlements.plan.code, (plan) => {
    if (feature === "research") return plan.features.research_enabled;
    if (feature === "prompt_improvement") return plan.features.prompt_improvement_enabled;
    return plan.features.file_analysis_enabled;
  });
  const label =
    feature === "research" ? "Web research" : feature === "prompt_improvement" ? "Improve" : "File analysis";
  return featureError(
    feature,
    `${label} is not available on the ${entitlements.plan.display_name} plan.`,
    entitlements,
    recommended,
  );
}

export function allowanceAccessError(
  meter: SubscriptionMeterKey,
  requested: number,
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionError | null {
  if (!entitlements || requested <= 0) return null;
  const allowance = entitlements.allowances[meter];
  if (!allowance) {
    return configurationError(`The ${meter} allowance could not be verified safely.`);
  }
  if (allowance.remaining >= requested) return null;

  const recommended = recommendedPlan(plans, entitlements.plan.code, (plan) => {
    const limit = publicAllowanceLimit(plan.allowances, meter);
    return limit !== null && limit > allowance.limit;
  });
  return localSubscriptionDenial({
    code: "insufficient_credits",
    message: `The ${entitlements.plan.display_name} plan has no ${METER_LABELS[meter]}s remaining.`,
    details: {
      meter,
      current_plan: entitlements.plan.code,
      recommended_plan: recommended,
      used: allowance.used,
      limit: allowance.limit,
      remaining: allowance.remaining,
      reset_at: entitlements.period.ends_at,
    },
  });
}

export function fileSelectionAccessError(
  files: File[],
  existingCount: number,
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionError | null {
  if (!entitlements || files.length === 0) return null;
  const featureDenied = featureAccessError("file_analysis", entitlements, plans);
  if (featureDenied) return featureDenied;

  const requestedCount = existingCount + files.length;
  if (requestedCount > entitlements.limits.max_files_per_request) {
    return featureError(
      "attachment_count",
      `The ${entitlements.plan.display_name} plan supports up to ${entitlements.limits.max_files_per_request} files per request.`,
      entitlements,
      null,
    );
  }

  const oversized = files.find((file) => file.size > entitlements.limits.max_file_bytes);
  if (oversized) {
    return featureError(
      "attachment_size",
      `${oversized.name} exceeds your plan's ${formatBytes(entitlements.limits.max_file_bytes)} per-file limit.`,
      entitlements,
      null,
    );
  }

  return null;
}

export function submitAccessError(options: {
  mode: "single" | "compare";
  smartMode: boolean;
  selectedModelKey: string;
  compareModelKeys: [string, string, string];
  models: ModelCatalogItem[];
  researchEnabled: boolean;
  optimizeEnabled: boolean;
  attachmentCount: number;
  entitlements: EntitlementsResponse | null;
  plans: BillingPlansResponse | null;
}): SubscriptionError | null {
  const { entitlements, plans } = options;
  if (!entitlements) return null;

  const activeKeys =
    options.mode === "compare"
      ? options.compareModelKeys.filter(Boolean)
      : options.smartMode
        ? []
        : [options.selectedModelKey];
  const targets = activeKeys.map((key) =>
    options.models.find((model) => modelKey(model) === key),
  );

  if (options.mode === "compare") {
    const compareDenied = compareTargetAccessError(activeKeys.length, entitlements, plans);
    if (compareDenied) return compareDenied;
  }
  for (const target of targets) {
    const denied = modelAccessError(target, entitlements, plans);
    if (denied) return denied;
  }

  const allowanceDenied = allowanceAccessError("ai_credits", 1, entitlements, plans);
  if (allowanceDenied) return allowanceDenied;

  if (options.researchEnabled) {
    const denied = featureAccessError("research", entitlements, plans);
    if (denied) return denied;
  }
  if (options.optimizeEnabled) {
    const denied = featureAccessError("prompt_improvement", entitlements, plans);
    if (denied) return denied;
  }
  if (options.attachmentCount > 0) {
    const denied = featureAccessError("file_analysis", entitlements, plans);
    if (denied) return denied;
    if (options.attachmentCount > entitlements.limits.max_files_per_request) {
      return featureError(
        "attachment_count",
        `The ${entitlements.plan.display_name} plan supports up to ${entitlements.limits.max_files_per_request} files per request.`,
        entitlements,
        null,
      );
    }
  }
  return null;
}

export function requiredPlanForModel(
  billingClass: ModelBillingClass,
  entitlements: EntitlementsResponse | null,
  plans: BillingPlansResponse | null,
): SubscriptionPlanCode | null {
  if (!entitlements) return null;
  return recommendedPlan(
    plans,
    entitlements.plan.code,
    (plan) => plan.features.allowed_billing_classes.includes(billingClass),
  );
}

function featureError(
  feature: FeatureKey,
  message: string,
  entitlements: EntitlementsResponse,
  recommendedPlanCode: SubscriptionPlanCode | null,
): SubscriptionError {
  return localSubscriptionDenial({
    code: "feature_not_in_plan",
    message,
    details: {
      feature,
      current_plan: entitlements.plan.code,
      recommended_plan: recommendedPlanCode,
      reset_at: entitlements.period.ends_at,
    },
  });
}

function configurationError(message: string): SubscriptionError {
  return new SubscriptionError({
    code: "subscription_configuration_error",
    message,
    status: 500,
    kind: "configuration",
    retryable: false,
  });
}

function recommendedPlan(
  plans: BillingPlansResponse | null,
  currentPlan: SubscriptionPlanCode,
  predicate: (plan: BillingPlansResponse["plans"][number]) => boolean,
): SubscriptionPlanCode | null {
  if (!plans) return null;
  const currentIndex = plans.plans.findIndex((plan) => plan.code === currentPlan);
  return plans.plans.slice(Math.max(0, currentIndex + 1)).find(predicate)?.code ?? null;
}

function publicAllowanceLimit(
  allowances: BillingPlansResponse["plans"][number]["allowances"],
  meter: SubscriptionMeterKey,
): number | null {
  return allowances[meter];
}

function modelKey(model: ModelCatalogItem): string {
  return `${model.provider}:${model.model}`;
}

function isBillingClass(value: unknown): value is ModelBillingClass {
  return (
    value === "economical" ||
    value === "standard" ||
    value === "advanced" ||
    value === "premium"
  );
}

function formatBytes(value: number): string {
  if (value >= 1_000_000) return `${Math.round(value / 1_000_000)} MB`;
  if (value >= 1_000) return `${Math.round(value / 1_000)} KB`;
  return `${value} bytes`;
}
