import { describe, it, expect } from "vitest";
import {
  parseModelKey,
  hasProvider,
  deriveSmartMode,
  isManualOverrideActive,
  isModelDropdownVisible,
  resolveManualSelection,
  toModelKey,
} from "../hooks/useSmartRouting";

describe("parseModelKey", () => {
  it("splits provider:model correctly", () => {
    expect(parseModelKey("openai:gpt-4o")).toEqual({ provider: "openai", model: "gpt-4o" });
  });

  it("returns empty provider when no colon", () => {
    expect(parseModelKey("gpt-4o")).toEqual({ provider: "", model: "gpt-4o" });
  });

  it("handles empty string", () => {
    expect(parseModelKey("")).toEqual({ provider: "", model: "" });
  });
});

describe("hasProvider", () => {
  it("returns true when key has provider", () => {
    expect(hasProvider("openai:gpt-4o")).toBe(true);
  });

  it("returns false for bare model name", () => {
    expect(hasProvider("gpt-4o")).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(hasProvider("")).toBe(false);
  });
});

describe("deriveSmartMode", () => {
  it("smart mode on when no provider selected", () => {
    expect(deriveSmartMode("")).toBe(true);
  });

  it("smart mode off when provider:model selected", () => {
    expect(deriveSmartMode("openai:gpt-4o")).toBe(false);
  });
});

describe("isManualOverrideActive", () => {
  it("true when single mode, not smart, has key", () => {
    expect(isManualOverrideActive("single", false, "openai:gpt-4o")).toBe(true);
  });

  it("false when smart mode active", () => {
    expect(isManualOverrideActive("single", true, "openai:gpt-4o")).toBe(false);
  });

  it("false in compare mode", () => {
    expect(isManualOverrideActive("compare", false, "openai:gpt-4o")).toBe(false);
  });
});

describe("isModelDropdownVisible", () => {
  it("visible in single mode when not smart", () => {
    expect(isModelDropdownVisible("single", false)).toBe(true);
  });

  it("hidden in single mode when smart", () => {
    expect(isModelDropdownVisible("single", true)).toBe(false);
  });

  it("hidden in compare mode", () => {
    expect(isModelDropdownVisible("compare", false)).toBe(false);
  });
});

describe("resolveManualSelection", () => {
  it("uses selectedKey when it has provider", () => {
    expect(resolveManualSelection("openai:gpt-4o", "gemini:gemini-pro")).toBe("openai:gpt-4o");
  });

  it("falls back to fallbackKey when selectedKey is empty", () => {
    expect(resolveManualSelection("", "gemini:gemini-pro")).toBe("gemini:gemini-pro");
  });
});

describe("toModelKey", () => {
  it("builds composite key", () => {
    expect(toModelKey("openai", "gpt-4o")).toBe("openai:gpt-4o");
  });
});
