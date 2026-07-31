import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ModelSelector } from "../components/composer/ModelSelector";
import type { ModelCatalogItem } from "../types";

const models = [
  model("openai", "gpt-5.1"),
  model("claude", "claude-sonnet-4-5"),
  model("deepseek", "deepseek-chat"),
  model("gemini", "gemini-2.5-flash"),
  model("grok", "grok-4"),
];

describe("ModelSelector", () => {
  it("uses the shared logo picker while preserving the native select contract", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { container } = render(
      <ModelSelector
        id="singleModel"
        label="Using"
        models={models}
        value="openai:gpt-5.1"
        onChange={onChange}
      />,
    );

    const nativeSelect = container.querySelector<HTMLSelectElement>("#singleModel");
    expect(nativeSelect).toHaveValue("openai:gpt-5.1");
    expect(nativeSelect?.querySelectorAll("option")).toHaveLength(5);

    await user.click(screen.getByRole("button", { name: /Using: GPT-5\.1/ }));
    const listbox = screen.getByRole("listbox", { name: "Using options" });

    expect(within(listbox).getByText("Claude Sonnet")).toBeInTheDocument();
    expect(within(listbox).getByText(/claude-sonnet-4-5 · High credit use/)).toBeInTheDocument();
    const deepSeekLogo = listbox.querySelector<HTMLImageElement>(
      'img[src*="domain_url=deepseek.com"]',
    );
    const geminiLogo = listbox.querySelector<HTMLImageElement>(
      'img[src*="domain_url=gemini.google.com"]',
    );
    const grokLogo = listbox.querySelector<HTMLImageElement>(
      'img[src*="domain_url=grok.com"]',
    );
    expect(deepSeekLogo).toHaveAttribute("width", "20");
    expect(deepSeekLogo).toHaveAttribute("height", "20");
    expect(geminiLogo).toHaveAttribute("width", "20");
    expect(geminiLogo).toHaveAttribute("height", "20");
    expect(grokLogo).toHaveAttribute("width", "20");
    expect(grokLogo).toHaveAttribute("height", "20");

    await user.click(within(listbox).getByRole("option", { name: /DeepSeek Chat/ }));
    expect(onChange).toHaveBeenCalledWith("deepseek:deepseek-chat");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});

function model(provider: string, name: string): ModelCatalogItem {
  return {
    provider,
    model: name,
    tier: "frontier",
    billing_class: "advanced",
    access_category: "advanced",
    input_credit_multiplier: 3,
    output_credit_multiplier: 12,
    credit_usage_label: "High",
    credit_pricing_version: "2026-07-29",
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_limit: 128000,
    tags: [],
    enabled: true,
    supports_image_input: false,
    supported_attachment_mime_types: [],
  };
}
