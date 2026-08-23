import { describe, expect, it } from "vitest";

import { DEFAULT_MODELS } from "../config/defaultModels";

describe("model billing classes", () => {
  it("keeps offline fallback models explicitly credit-classified", () => {
    expect(DEFAULT_MODELS).not.toHaveLength(0);
    expect(
      DEFAULT_MODELS.every(
        (model) =>
          model.billing_class === model.access_category &&
          (model.input_credit_multiplier ?? 0) > 0 &&
          (model.output_credit_multiplier ?? 0) > 0 &&
          Boolean(model.credit_usage_label) &&
          Boolean(model.credit_pricing_version),
      ),
    ).toBe(true);
    expect(
      DEFAULT_MODELS.find((model) => model.model === "deepseek-v4-flash")?.billing_class,
    ).toBe("economical");
  });
});
