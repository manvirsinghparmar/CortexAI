import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CompareSelector } from "../components/composer/CompareSelector";
import type { ModelCatalogItem } from "../types";

const models = [
  model("openai", "gpt-5.1"),
  model("claude", "claude-sonnet-4-5"),
  model("deepseek", "deepseek-chat"),
  model("gemini", "gemini-2.5-flash"),
];

describe("CompareSelector", () => {
  it("renders readable labels, exact model IDs, and provider logos", async () => {
    const user = userEvent.setup();
    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Compare model 1:/ }));
    const listbox = screen.getByRole("listbox", { name: "Compare model 1 options" });

    expect(within(listbox).getByText("GPT-5.1")).toBeInTheDocument();
    expect(within(listbox).getByText("gpt-5.1")).toBeInTheDocument();
    expect(within(listbox).getByText("Claude Sonnet")).toBeInTheDocument();
    expect(listbox.querySelectorAll("img").length).toBeGreaterThan(0);
  });

  it("selects a model and disables models already used in another slot", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Compare model 1:/ }));
    const listbox = screen.getByRole("listbox", { name: "Compare model 1 options" });
    expect(
      within(listbox).getByRole("option", { name: /Claude Sonnet/ }),
    ).toBeDisabled();

    await user.click(within(listbox).getByRole("option", { name: /Gemini Flash/ }));
    expect(onChange).toHaveBeenCalledWith(0, "gemini:gemini-2.5-flash");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
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
