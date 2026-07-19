import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { uploadFile } from "../api/files";
import { AttachmentStrip } from "../components/composer/AttachmentStrip";
import { CompareSelector } from "../components/composer/CompareSelector";
import { ModelSelector } from "../components/composer/ModelSelector";
import { PromptComposer } from "../components/composer/PromptComposer";
import { PlanBadge } from "../components/subscription/PlanBadge";
import { SubscriptionBanner } from "../components/subscription/SubscriptionBanner";
import { UpgradeDialog } from "../components/subscription/UpgradeDialog";
import { UsageAllowance } from "../components/subscription/UsageAllowance";
import { DEFAULT_MODELS } from "../config/defaultModels";
import { useChatStore } from "../store/chatStore";
import { localSubscriptionDenial } from "../subscription/subscriptionErrors";
import type {
  BillingPlansResponse,
  EntitlementsResponse,
  ModelBillingClass,
  ModelCatalogItem,
} from "../types";

vi.mock("../api/files", () => ({
  uploadFile: vi.fn(),
  deleteFile: vi.fn().mockResolvedValue(undefined),
  fetchFileStatus: vi.fn(),
}));

describe("subscription feature gating", () => {
  beforeEach(() => {
    useChatStore.getState().startNewChat();
    useChatStore.setState({
      mode: "single",
      smartMode: false,
      researchMode: false,
      compareResearchMode: false,
      optimizeMode: false,
      selectedModelKey: "openai:gpt-5.1",
      compareModelKeys: ["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""],
      subscriptionError: null,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders reusable plan, status, and allowance controls accessibly", async () => {
    const user = userEvent.setup();
    const manage = vi.fn();
    const entitlements = entitlementFixture({
      status: "past_due",
      grace_until: "2026-08-03T00:00:00Z",
    });

    render(
      <>
        <PlanBadge label="Free" tone="current" />
        <SubscriptionBanner entitlements={entitlements} onManageBilling={manage} />
        <UsageAllowance entitlements={entitlements} />
      </>,
    );

    expect(screen.getAllByText("Free")[0]!.closest("[data-plan-badge]"))
      .toHaveAttribute("data-plan-badge", "current");
    expect(screen.getByRole("alert", { name: "Subscription status" })).toHaveTextContent(
      "Update your payment method",
    );
    expect(screen.getByRole("heading", { name: "Plan allowances" })).toBeInTheDocument();
    expect(
      screen.getByRole("progressbar", { name: "Model responses: 20 left of 30" }),
    ).toHaveAttribute("aria-valuenow", "10");
    expect(screen.getByText("29 MB left of 30 MB")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Manage billing" }));
    expect(manage).toHaveBeenCalledTimes(1);
  });

  it("traps a contextual denial in an accessible, keyboard-dismissible dialog", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const viewPlans = vi.fn();
    const error = localSubscriptionDenial({
      code: "model_not_in_plan",
      message: "gpt-ultra is not available on the Free plan.",
      details: { current_plan: "free", recommended_plan: "pro" },
    });

    render(
      <UpgradeDialog
        error={error}
        onClose={onClose}
        onViewPlans={viewPlans}
        onManageBilling={vi.fn()}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "This model is locked on your plan" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Close subscription message" })).toHaveFocus();
    });
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(within(dialog).getByRole("button", { name: "View Pro" })).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(screen.getByRole("button", { name: "Close subscription message" })).toHaveFocus();
    await user.click(within(dialog).getByRole("button", { name: "View Pro" }));
    expect(viewPlans).toHaveBeenCalledTimes(1);

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps locked models visible and explains the lock instead of selecting them", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const onLocked = vi.fn();
    const models = [model("standard-model", "standard"), model("ultra-model", "ultra")];

    render(
      <ModelSelector
        models={models}
        value="openai:standard-model"
        onChange={onChange}
        lockedKeys={["openai:ultra-model"]}
        lockedLabels={{ "openai:ultra-model": "Pro" }}
        onLockedSelect={onLocked}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /Model: ChatGPT \(standard-model\)/ }),
    );
    const locked = within(screen.getByRole("listbox")).getByRole("option", {
      name: /ChatGPT.*ultra-model.*Pro/,
    });
    expect(locked).toHaveAttribute("aria-disabled", "true");
    expect(locked).not.toBeDisabled();
    expect(
      document.querySelector<HTMLOptionElement>(
        '#modelSelector option[value="openai:ultra-model"]',
      ),
    ).toBeDisabled();
    await user.click(locked);

    expect(onLocked).toHaveBeenCalledWith("openai:ultra-model");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows the third-model plan CTA without adding a target", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const onTargetLimit = vi.fn();

    render(
      <CompareSelector
        models={DEFAULT_MODELS}
        keys={["openai:gpt-5.1", "claude:claude-sonnet-4-5", ""]}
        onChange={onChange}
        maxTargets={2}
        thirdTargetPlanLabel="Pro"
        onTargetLimit={onTargetLimit}
      />,
    );

    const cta = screen.getByRole("button", { name: "Unlock third comparison model" });
    expect(cta).toHaveTextContent("Add third model");
    expect(cta).toHaveTextContent("Pro");
    await user.click(cta);
    expect(onTargetLimit).toHaveBeenCalledTimes(1);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("explains exhausted Web access without changing or clearing the draft", async () => {
    const user = userEvent.setup();
    const entitlements = entitlementFixture();
    entitlements.allowances.research_turns = {
      used: 5,
      reserved: 0,
      limit: 5,
      remaining: 0,
    };
    useChatStore.setState({ prompt: "Keep this draft" });

    render(
      <PromptComposer
        models={DEFAULT_MODELS}
        subscription={{ plans: plansFixture(), entitlements }}
      />,
    );

    const research = screen.getByRole("switch", { name: "Research mode" });
    expect(research).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("tooltip", { name: /0 left this period/ })).toBeInTheDocument();
    await user.click(research);

    expect(useChatStore.getState().subscriptionError?.code).toBe(
      "monthly_allowance_exhausted",
    );
    expect(useChatStore.getState().prompt).toBe("Keep this draft");
    expect(research).toHaveAttribute("aria-checked", "false");
  });

  it("blocks over-limit files before upload and keeps existing attachments", async () => {
    const entitlements = entitlementFixture();
    const oversized = new File([new Uint8Array(11_000_000)], "large.pdf", {
      type: "application/pdf",
    });

    render(<AttachmentStrip entitlements={entitlements} plans={plansFixture()} />);
    expect(screen.getByText("Up to 1 file · 10 MB each")).toBeInTheDocument();

    fireEvent.change(document.querySelector("#attachmentInput")!, {
      target: { files: [oversized] },
    });

    await waitFor(() => {
      expect(useChatStore.getState().subscriptionError?.details.feature).toBe(
        "attachment_size",
      );
    });
    expect(uploadFile).not.toHaveBeenCalled();
    expect(useChatStore.getState().attachments).toEqual([]);
  });

  it("keeps allowance details and denial actions available at a phone viewport", () => {
    const originalWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 360 });
    const error = localSubscriptionDenial({
      code: "feature_not_in_plan",
      message: "Three-model Compare is not available on the Free plan.",
      details: {
        feature: "compare_model_count",
        current_plan: "free",
        recommended_plan: "pro",
      },
    });

    try {
      render(
        <>
          <UsageAllowance entitlements={entitlementFixture()} compact />
          <UpgradeDialog
            error={error}
            onClose={vi.fn()}
            onViewPlans={vi.fn()}
            onManageBilling={vi.fn()}
          />
        </>,
      );

      expect(screen.getAllByRole("progressbar")).toHaveLength(7);
      expect(screen.getByRole("dialog", { name: "Three-model Compare requires Pro" }))
        .toBeVisible();
      expect(screen.getByRole("button", { name: "View Pro" })).toBeVisible();
    } finally {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: originalWidth,
      });
    }
  });
});

function entitlementFixture(
  planOverrides: Partial<EntitlementsResponse["plan"]> = {},
): EntitlementsResponse {
  const counter = (used: number, limit: number) => ({
    used,
    reserved: 0,
    limit,
    remaining: Math.max(0, limit - used),
  });
  return {
    plan: {
      code: "free",
      display_name: "Free",
      status: "free",
      source: "default",
      renews_at: "2026-08-19T00:00:00Z",
      cancel_at_period_end: false,
      grace_until: null,
      ...planOverrides,
    },
    features: {
      compare_enabled: true,
      max_compare_models: 2,
      research_enabled: true,
      prompt_improvement_enabled: true,
      file_analysis_enabled: true,
      usage_export_enabled: true,
      saved_history_enabled: true,
      models_catalog_enabled: true,
    },
    model_access: { allowed_billing_classes: ["standard", "advanced"] },
    limits: { max_files_per_request: 1, max_file_bytes: 10_000_000 },
    allowances: {
      model_responses: counter(10, 30),
      advanced_model_responses: counter(1, 5),
      ultra_model_responses: counter(0, 0),
      research_turns: counter(1, 5),
      optimization_turns: counter(2, 10),
      file_analysis_turns: counter(1, 3),
      uploaded_bytes: counter(1_000_000, 30_000_000),
    },
    period: {
      starts_at: "2026-07-19T00:00:00Z",
      ends_at: "2026-08-19T00:00:00Z",
    },
  };
}

function plansFixture(): BillingPlansResponse {
  const plan = (
    code: "free" | "plus" | "pro",
    classes: ModelBillingClass[],
    maxCompare: number,
  ) => ({
    code,
    display_name: `${code.charAt(0).toUpperCase()}${code.slice(1)}`,
    monthly_price: code === "free" ? 0 : code === "plus" ? 6.99 : 12.99,
    recommended: code === "plus",
    features: {
      max_compare_models: maxCompare,
      research_enabled: true,
      prompt_improvement_enabled: true,
      file_analysis_enabled: true,
      allowed_billing_classes: classes,
    },
    allowances: {
      model_responses: code === "free" ? 30 : code === "plus" ? 400 : 1200,
      advanced_model_responses: code === "free" ? 5 : code === "plus" ? 75 : 300,
      ultra_model_responses: code === "pro" ? 40 : 0,
      research_turns: code === "free" ? 5 : code === "plus" ? 50 : 200,
      optimization_turns: code === "free" ? 10 : code === "plus" ? 200 : 500,
      file_analysis_turns: code === "free" ? 3 : code === "plus" ? 30 : 100,
    },
  });
  return {
    currency: "USD",
    billing_period: "monthly",
    billing_enabled: true,
    plans: [
      plan("free", ["standard", "advanced"], 2),
      plan("plus", ["standard", "advanced"], 2),
      plan("pro", ["standard", "advanced", "ultra"], 3),
    ],
  };
}

function model(name: string, billingClass: ModelBillingClass): ModelCatalogItem {
  return {
    provider: "openai",
    model: name,
    tier: "frontier",
    billing_class: billingClass,
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_limit: 128_000,
    tags: [],
    enabled: true,
    supports_image_input: false,
    supported_attachment_mime_types: [],
  };
}
