import { describe, expect, it } from "vitest";

import { DEFAULT_MODELS } from "../config/defaultModels";

describe("model billing classes", () => {
  it("keeps offline fallback models conservatively classified", () => {
    expect(DEFAULT_MODELS).not.toHaveLength(0);
    expect(DEFAULT_MODELS.every((model) => model.billing_class === "advanced")).toBe(true);
  });
});
