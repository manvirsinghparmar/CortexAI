import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ModelSelector } from "../components/composer/ModelSelector";
import type { ModelCatalogItem } from "../types";

const models = [
  model("openai", "gpt-5.1"),
  model("openai", "gpt-4.1-mini"),
  model("claude", "claude-sonnet-4-5"),
  model("deepseek", "deepseek-chat"),
  model("gemini", "gemini-2.5-flash"),
  model("grok", "grok-4"),
];

describe("ModelSelector", () => {
  it("shows providers first, then models from only the chosen provider", async () => {
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
    expect(nativeSelect?.querySelectorAll("option")).toHaveLength(6);

    await user.click(screen.getByRole("button", { name: /Using: GPT-5\.1/ }));
    const listbox = screen.getByRole("listbox", { name: "Using options" });

    expect(listbox).toHaveAttribute("data-picker-view", "providers");
    expect(listbox).toHaveAttribute("data-picker-interaction", "drilldown");
    expect(within(listbox).getByText("Choose a provider")).toBeInTheDocument();
    expect(
      within(listbox).getByRole("option", {
        name: /ChatGPT, 2 models, current provider/,
      }),
    ).toHaveFocus();
    expect(within(listbox).queryByText("Claude Sonnet")).not.toBeInTheDocument();

    const deepSeekLogo = listbox.querySelector<HTMLImageElement>(
      'img[src*="domain_url=deepseek.com"]',
    );
    const geminiLogo = listbox.querySelector<HTMLImageElement>(
      'img[src*="domain_url=gemini.google.com"]',
    );
    const grokLogo = listbox.querySelector<HTMLImageElement>('img[src*="domain_url=grok.com"]');
    expect(deepSeekLogo).toHaveAttribute("width", "20");
    expect(deepSeekLogo).toHaveAttribute("height", "20");
    expect(geminiLogo).toHaveAttribute("width", "20");
    expect(geminiLogo).toHaveAttribute("height", "20");
    expect(grokLogo).toHaveAttribute("width", "20");
    expect(grokLogo).toHaveAttribute("height", "20");

    await user.click(within(listbox).getByRole("option", { name: /Claude, 1 model/ }));
    expect(listbox).toHaveAttribute("data-picker-view", "models");
    expect(within(listbox).getByText("Claude Sonnet")).toBeInTheDocument();
    expect(within(listbox).getByText(/claude-sonnet-4-5 · High credit use/)).toBeInTheDocument();
    expect(within(listbox).queryByText("DeepSeek Chat")).not.toBeInTheDocument();

    await user.click(within(listbox).getByRole("option", { name: "Back to providers" }));
    await user.click(within(listbox).getByRole("option", { name: /DeepSeek, 1 model/ }));
    await user.click(within(listbox).getByRole("option", { name: /DeepSeek Chat/ }));

    expect(onChange).toHaveBeenCalledWith("deepseek:deepseek-chat");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("previews desktop models on provider hover and dismisses the preview on hover away", () => {
    vi.useFakeTimers();
    const matchMedia = vi.spyOn(window, "matchMedia").mockImplementation(
      (query: string) =>
        ({
          matches: query === "(hover: hover) and (pointer: fine) and (min-width: 761px)",
          media: query,
          onchange: null,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
          dispatchEvent: vi.fn(),
        }) as unknown as MediaQueryList,
    );

    try {
      render(
        <ModelSelector
          id="singleModel"
          label="Using"
          models={models}
          value="openai:gpt-5.1"
          onChange={vi.fn()}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: /Using: GPT-5\.1/ }));
      const listbox = screen.getByRole("listbox", { name: "Using options" });
      const claudeProvider = within(listbox).getByRole("option", { name: /Claude, 1 model/ });

      expect(listbox).toHaveAttribute("data-picker-interaction", "hover");
      fireEvent.pointerEnter(claudeProvider, { pointerType: "mouse" });

      expect(listbox).toHaveAttribute("data-picker-view", "models");
      expect(within(listbox).getByText("Choose a provider")).toBeInTheDocument();
      expect(within(listbox).getByText("Claude Sonnet")).toBeInTheDocument();

      fireEvent.pointerLeave(listbox, { pointerType: "mouse" });
      act(() => vi.advanceTimersByTime(140));

      expect(listbox).toHaveAttribute("data-picker-view", "providers");
      expect(within(listbox).queryByText("Claude Sonnet")).not.toBeInTheDocument();
    } finally {
      matchMedia.mockRestore();
      vi.useRealTimers();
    }
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
