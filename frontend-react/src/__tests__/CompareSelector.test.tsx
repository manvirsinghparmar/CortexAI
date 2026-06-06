import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CompareSelector } from "../components/composer/CompareSelector";
import type { ModelCatalogItem } from "../types";

const models: ModelCatalogItem[] = [
  model("openai", "gpt-4o"),
  model("gemini", "gemini-2.5-flash"),
  model("grok", "grok-4-1-fast-non-reasoning"),
];

describe("CompareSelector", () => {
  it("opens a model choice menu instead of auto-adding a target", () => {
    const onChange = vi.fn();

    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-4o", "gemini:gemini-2.5-flash", ""]}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Choose a model to add" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("menu", { name: "Available compare models" })).toBeDefined();

    fireEvent.click(screen.getByRole("menuitem", { name: /Grok 4.1 Fast/i }));

    expect(onChange).toHaveBeenCalledWith(2, "grok:grok-4-1-fast-non-reasoning");
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
