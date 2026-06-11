import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ExampleChips } from "../components/shared/ExampleChips";
import { useChatStore } from "../store/chatStore";

describe("ExampleChips", () => {
  beforeEach(() => {
    useChatStore.setState({
      mode: "single",
      prompt: "",
      turns: [],
      streaming: false,
    });
  });

  it("explains the Ask workspace and offers a range of useful prompts", () => {
    render(<ExampleChips />);

    expect(screen.getByText("Your AI workspace")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Your AI workspace for answers, analysis, and model comparison",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Ask questions, analyze files, generate content/)).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(4);
  });

  it("fills the composer when an Ask example is selected", async () => {
    const user = userEvent.setup();
    render(<ExampleChips />);

    await user.click(
      screen.getByRole("button", {
        name: "Summarize this document into key takeaways",
      }),
    );

    expect(useChatStore.getState().prompt).toBe(
      "Summarize this document into key takeaways",
    );
  });

  it("explains Compare mode and fills the prompt without changing modes", async () => {
    const user = userEvent.setup();
    useChatStore.setState({ mode: "compare" });
    render(<ExampleChips />);

    expect(screen.getByText("Compare mode")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Ask once. Compare answers across models.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Compare accuracy, depth, speed, tone, and usefulness/)).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(3);

    await user.click(
      screen.getByRole("button", {
        name: "Find the strongest solution for this bug",
      }),
    );

    expect(useChatStore.getState().mode).toBe("compare");
    expect(useChatStore.getState().prompt).toBe(
      "Find the strongest solution for this bug",
    );
  });
});
