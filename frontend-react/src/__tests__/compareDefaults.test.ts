import { describe, expect, it } from "vitest";
import {
  removeCompareModelKey,
  resolveAddedCompareModelKey,
  resolveCompareModelKeys,
} from "../config/compareDefaults";
import type { ModelCatalogItem } from "../types";

describe("compare model defaults", () => {
  it("selects GPT-5.1 and Claude Sonnet 4.5 by name, independent of catalog order", () => {
    const models = [
      model("claude", "claude-haiku-4-5"),
      model("deepseek", "deepseek-chat"),
      model("claude", "claude-sonnet-4-5"),
      model("openai", "gpt-5.1"),
    ];

    expect(resolveCompareModelKeys(models, ["", "", ""])).toEqual([
      "openai:gpt-5.1",
      "claude:claude-sonnet-4-5",
      "",
    ]);
  });

  it("preserves valid manual selections", () => {
    const models = [
      model("gemini", "gemini-2.5-flash"),
      model("openai", "gpt-5.1"),
      model("claude", "claude-sonnet-4-5"),
    ];

    expect(
      resolveCompareModelKeys(models, [
        "gemini:gemini-2.5-flash",
        "claude:claude-sonnet-4-5",
        "",
      ]),
    ).toEqual([
      "gemini:gemini-2.5-flash",
      "claude:claude-sonnet-4-5",
      "",
    ]);
  });

  it("uses DeepSeek Chat when a third model is added", () => {
    const models = [
      model("openai", "gpt-5.1"),
      model("claude", "claude-sonnet-4-5"),
      model("deepseek", "deepseek-chat"),
    ];

    expect(
      resolveAddedCompareModelKey(models, [
        "openai:gpt-5.1",
        "claude:claude-sonnet-4-5",
        "",
      ]),
    ).toBe("deepseek:deepseek-chat");
  });

  it("falls back to available distinct models when a preference is disabled", () => {
    const models = [
      model("gemini", "gemini-2.5-flash"),
      model("claude", "claude-haiku-4-5"),
      model("grok", "grok-4"),
    ];

    expect(resolveCompareModelKeys(models, ["", "", ""])).toEqual([
      "gemini:gemini-2.5-flash",
      "claude:claude-haiku-4-5",
      "",
    ]);
    expect(
      resolveAddedCompareModelKey(models, [
        "gemini:gemini-2.5-flash",
        "claude:claude-haiku-4-5",
        "",
      ]),
    ).toBe("grok:grok-4");
  });

  it.each([
    [0, ["claude:claude-sonnet-4-5", "deepseek:deepseek-chat", ""]],
    [1, ["openai:gpt-5.1", "deepseek:deepseek-chat", ""]],
    [2, ["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]],
  ] as const)("removes and compacts compare slot %i", (removeIndex, expected) => {
    expect(
      removeCompareModelKey(
        [
          "openai:gpt-5.1",
          "claude:claude-sonnet-4-5",
          "deepseek:deepseek-chat",
        ],
        removeIndex,
      ),
    ).toEqual(expected);
  });
});

function model(provider: string, name: string): ModelCatalogItem {
  return {
    provider,
    model: name,
    tier: "frontier",
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_limit: 128000,
    tags: [],
    enabled: true,
    supports_image_input: false,
    supported_attachment_mime_types: [],
  };
}
