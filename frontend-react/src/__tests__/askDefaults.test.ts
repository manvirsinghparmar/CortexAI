import { describe, expect, it } from "vitest";
import {
  DEFAULT_ASK_MODEL_KEYS_BY_PLAN,
  resolveAskModelKey,
} from "../config/askDefaults";
import { DEFAULT_MODELS } from "../config/defaultModels";
import type {
  ModelBillingClass,
  SubscriptionPlanCode,
} from "../types";

describe("Ask model defaults", () => {
  it.each([
    ["free", ["economical", "standard"], "openai:gpt-5.6-luna"],
    ["plus", ["economical", "standard", "advanced"], "claude:claude-sonnet-4-6"],
    [
      "pro",
      ["economical", "standard", "advanced", "premium"],
      "openai:gpt-5.6-terra",
    ],
  ] as Array<[SubscriptionPlanCode, ModelBillingClass[], string]>)(
    "selects the configured %s default from entitled models",
    (planCode, allowedBillingClasses, expectedKey) => {
      expect(DEFAULT_ASK_MODEL_KEYS_BY_PLAN[planCode]).toBe(expectedKey);
      expect(
        resolveAskModelKey(DEFAULT_MODELS, "", planCode, allowedBillingClasses),
      ).toBe(expectedKey);
    },
  );

  it("preserves a valid manual selection", () => {
    expect(
      resolveAskModelKey(
        DEFAULT_MODELS,
        "deepseek:deepseek-v4-flash",
        "pro",
        ["economical", "standard", "advanced", "premium"],
      ),
    ).toBe("deepseek:deepseek-v4-flash");
  });
});
