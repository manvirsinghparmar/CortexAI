import { fireEvent, render, screen, within } from "@testing-library/react";
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
  it("drills from provider choices into readable model details", async () => {
    const user = userEvent.setup();
    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Compare model 1:/ }));
    const listbox = screen.getByRole("listbox", {
      name: "Compare model 1 options",
    });

    expect(listbox.parentElement).toBe(document.body);
    expect(listbox).toHaveAttribute("data-picker-view", "providers");
    expect(within(listbox).getByRole("option", { name: /ChatGPT/ })).toBeVisible();
    expect(within(listbox).getByRole("option", { name: /Claude/ })).toBeVisible();
    expect(listbox.querySelectorAll("img").length).toBeGreaterThan(0);

    await user.click(within(listbox).getByRole("option", { name: /ChatGPT/ }));
    expect(listbox).toHaveAttribute("data-picker-view", "models");
    expect(within(listbox).getByText("GPT-5.1")).toBeInTheDocument();
    expect(within(listbox).getByText("gpt-5.1")).toBeInTheDocument();

    await user.click(within(listbox).getByRole("option", { name: "Back to providers" }));
    await user.click(within(listbox).getByRole("option", { name: /Claude/ }));
    expect(within(listbox).getByText("Claude Sonnet")).toBeInTheDocument();
  });

  it("renders one decorative connector between each active model", () => {
    const { rerender } = render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("compare-connector")).toHaveLength(1);
    expect(screen.getByTestId("compare-connector")).toHaveAttribute("aria-hidden", "true");

    rerender(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", "deepseek:deepseek-chat"]}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getAllByTestId("compare-connector")).toHaveLength(2);
  });

  it("selects within a provider and disables models used in another slot", async () => {
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
    const listbox = screen.getByRole("listbox", {
      name: "Compare model 1 options",
    });
    await user.click(within(listbox).getByRole("option", { name: /Claude/ }));
    expect(within(listbox).getByRole("option", { name: /Claude Sonnet/ })).toBeDisabled();

    await user.click(within(listbox).getByRole("option", { name: "Back to providers" }));
    await user.click(within(listbox).getByRole("option", { name: /Gemini/ }));
    await user.click(within(listbox).getByRole("option", { name: /Gemini Flash/ }));
    expect(onChange).toHaveBeenCalledWith(0, "gemini:gemini-2.5-flash");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("keeps the synchronized native select usable for mobile model selection", () => {
    const onChange = vi.fn();
    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={onChange}
      />,
    );

    fireEvent.change(document.querySelector("#compareModel1")!, {
      target: { value: "gemini:gemini-2.5-flash" },
    });

    expect(onChange).toHaveBeenCalledWith(0, "gemini:gemini-2.5-flash");
  });

  it("keeps optional feature controls inside the compare toolbar", () => {
    render(
      <CompareSelector
        models={models}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={vi.fn()}
        trailingControls={<button type="button">Improve</button>}
      />,
    );

    const toolbar = screen.getByLabelText("Compare model selectors");
    expect(within(toolbar).getByRole("button", { name: "Improve" })).toBeInTheDocument();
    expect(
      within(toolbar).getByRole("button", {
        name: "Add model to comparison",
      }),
    ).toBeInTheDocument();
  });
});

function model(provider: string, name: string): ModelCatalogItem {
  return {
    provider,
    model: name,
    tier: "frontier",
    billing_class: "advanced",
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_limit: 128000,
    tags: [],
    enabled: true,
    supports_image_input: false,
    supported_attachment_mime_types: [],
  };
}
