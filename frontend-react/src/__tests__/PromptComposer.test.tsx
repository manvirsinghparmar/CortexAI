import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PromptComposer } from "../components/composer/PromptComposer";
import { DEFAULT_MODELS } from "../config/defaultModels";
import { useChatStore } from "../store/chatStore";
import type { FileUploadResponse } from "../types";

vi.mock("../api/files", () => ({
  uploadFile: vi.fn(),
  deleteFile: vi.fn().mockResolvedValue(undefined),
  fetchFileStatus: vi.fn(),
}));

describe("PromptComposer", () => {
  beforeEach(() => {
    useChatStore.setState({
      mode: "single",
      smartMode: true,
      researchMode: true,
      compareResearchMode: true,
      optimizeMode: false,
      selectedModelKey: "openai:gpt-5.1",
      compareModelKeys: [
        "openai:gpt-5.1",
        "claude:claude-sonnet-4-5",
        "",
      ],
      prompt: "",
      attachments: [],
      turns: [],
      activeTurnId: null,
      responses: [],
      streaming: false,
      streamingText: "",
      error: null,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("keeps the compact Ask composer controls in one shell", async () => {
    const user = userEvent.setup();
    useChatStore.setState({ attachments: [attachment()] });

    render(<PromptComposer models={DEFAULT_MODELS} />);

    const textarea = screen.getByRole("textbox", { name: "Prompt input" });
    const card = textarea.parentElement?.parentElement;
    const fileName = screen.getByText("long-mobile-design-reference.pdf");
    const attachButton = screen.getByRole("button", { name: "Attach files" });
    const smartSwitch = screen.getByRole("switch", { name: "Smart routing" });
    const researchSwitch = screen.getByRole("switch", { name: "Research mode" });
    const smartTooltip = screen.getByRole("tooltip", {
      name: "Gets you the best answer automatically",
    });
    const researchTooltip = screen.getByRole("tooltip", {
      name: "Uses latest information from the web",
    });
    const improveTooltip = screen.getByRole("tooltip", {
      name: "Helps you ask better for better results",
    });
    const sendButton = screen.getByRole("button", { name: "Send message" });

    expect(textarea).toHaveAttribute("rows", "1");
    expect(textarea).toHaveAttribute(
      "placeholder",
      "Ask anything . . .",
    );
    expect(card).toContainElement(fileName);
    expect(card).toContainElement(attachButton);
    expect(card).toContainElement(smartSwitch);
    expect(smartSwitch).toHaveAttribute("aria-describedby", smartTooltip.id);
    expect(researchSwitch).toHaveAttribute("aria-checked", "true");
    expect(researchSwitch).toHaveAttribute("aria-describedby", researchTooltip.id);
    expect(
      screen.getByRole("switch", { name: "Prompt optimization" }),
    ).toHaveAttribute("aria-describedby", improveTooltip.id);
    expect(card).toContainElement(sendButton);
    expect(screen.queryByRole("checkbox", { name: "Compare" })).not.toBeInTheDocument();
    expect(
      textarea.compareDocumentPosition(fileName) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    await user.click(
      screen.getByRole("button", { name: "Remove long-mobile-design-reference.pdf" }),
    );

    await waitFor(() => {
      expect(screen.queryByText("long-mobile-design-reference.pdf")).not.toBeInTheDocument();
    });
    expect(useChatStore.getState().attachments).toEqual([]);
  });

  it("starts Ask mode with Web enabled and preserves a manual off choice", async () => {
    const user = userEvent.setup();

    render(<PromptComposer models={DEFAULT_MODELS} />);

    const researchSwitch = screen.getByRole("switch", { name: "Research mode" });
    expect(researchSwitch).toHaveTextContent("Web");
    expect(researchSwitch).toHaveAttribute("aria-checked", "true");
    expect(useChatStore.getState().researchMode).toBe(true);

    await user.click(researchSwitch);

    expect(researchSwitch).toHaveAttribute("aria-checked", "false");
    expect(useChatStore.getState().researchMode).toBe(false);
  });

  it("uses the same shell in Compare mode without a redundant mode switch", () => {
    useChatStore.setState({ mode: "compare" });
    render(<PromptComposer models={DEFAULT_MODELS} />);

    expect(useChatStore.getState().mode).toBe("compare");
    expect(screen.getByLabelText("Compare model selectors")).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Smart routing" })).not.toBeInTheDocument();
    const sourcesSwitch = screen.getByRole("switch", { name: "Compare with sources" });
    const improveSwitch = screen.getByRole("switch", { name: "Prompt optimization" });
    expect(sourcesSwitch).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("tooltip", {
        name: "Uses latest information from the web",
      }).id,
    );
    expect(improveSwitch).toHaveAttribute(
      "aria-describedby",
      screen.getByRole("tooltip", {
        name: "Helps you ask better for better results",
      }).id,
    );
    expect(screen.queryByRole("checkbox", { name: "Compare" })).not.toBeInTheDocument();

    const textarea = screen.getByRole("textbox", { name: "Prompt input" });
    const card = textarea.parentElement?.parentElement;
    expect(textarea).toHaveAttribute(
      "placeholder",
      "Ask once and compare model responses",
    );
    expect(textarea).toHaveAttribute("rows", "1");
    expect(card).toContainElement(screen.getByLabelText("Compare model selectors"));
    expect(card).toContainElement(screen.getByRole("button", { name: "Send message" }));
  });

  it("shows a tapped feature tooltip for two seconds while toggling the chip", () => {
    vi.useFakeTimers();
    render(<PromptComposer models={DEFAULT_MODELS} />);

    const researchSwitch = screen.getByRole("switch", { name: "Research mode" });
    const tooltip = screen.getByRole("tooltip", {
      name: "Uses latest information from the web",
    });

    const touchPointerUp = new Event("pointerup", { bubbles: true });
    Object.defineProperty(touchPointerUp, "pointerType", { value: "touch" });
    fireEvent(researchSwitch, touchPointerUp);
    fireEvent.click(researchSwitch);

    expect(researchSwitch).toHaveAttribute("aria-checked", "false");
    expect(tooltip).toHaveAttribute("data-touch-visible", "true");

    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(tooltip).toHaveAttribute("data-touch-visible", "true");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(tooltip).toHaveAttribute("data-touch-visible", "false");
  });

  it("auto-grows longer prompts and caps the textarea height", async () => {
    render(<PromptComposer models={DEFAULT_MODELS} />);

    const textarea = screen.getByRole<HTMLTextAreaElement>("textbox", {
      name: "Prompt input",
    });
    Object.defineProperty(textarea, "scrollHeight", {
      configurable: true,
      value: 96,
    });

    fireEvent.change(textarea, { target: { value: "Line one\nLine two\nLine three" } });

    await waitFor(() => {
      expect(textarea.style.height).toBe("96px");
      expect(textarea.style.overflowY).toBe("hidden");
    });

    Object.defineProperty(textarea, "scrollHeight", {
      configurable: true,
      value: 220,
    });
    fireEvent.change(textarea, {
      target: { value: "Line one\nLine two\nLine three\nLine four" },
    });

    await waitFor(() => {
      expect(textarea.style.height).toBe("160px");
      expect(textarea.style.overflowY).toBe("auto");
    });
  });
});

function attachment(): FileUploadResponse {
  return {
    file_id: "file-1",
    original_filename: "long-mobile-design-reference.pdf",
    mime_type: "application/pdf",
    size_bytes: 59699,
    status: "ready",
    ingestion_meta: {},
    created_at: "2026-06-10T00:00:00.000Z",
    deduplicated: false,
  };
}
