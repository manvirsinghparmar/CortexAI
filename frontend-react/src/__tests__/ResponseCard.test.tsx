import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResponseCard } from "../components/results/ResponseCard";
import type { ChatResponse } from "../types";

describe("ResponseCard", () => {
  it("shows a friendly model name while retaining the exact API model ID", () => {
    const { container } = render(<ResponseCard response={response()} compact />);

    expect(screen.getByRole("heading", { name: "Claude Sonnet" })).toBeInTheDocument();
    expect(screen.getByText("claude-sonnet-4-5")).toBeInTheDocument();
    expect(container.querySelector('img[src*="claude.ai"]')).toBeInTheDocument();
  });

  it("falls back to the provider initial when the shared logo cannot load", () => {
    const { container } = render(<ResponseCard response={response()} compact />);
    const logo = container.querySelector<HTMLImageElement>('img[src*="claude.ai"]');

    expect(logo).not.toBeNull();
    fireEvent.error(logo!);

    expect(container.querySelector('img[src*="claude.ai"]')).not.toBeInTheDocument();
    expect(container.querySelector("header")).toHaveTextContent("C");
  });

  it("keeps compact actions accessible by name", () => {
    render(<ResponseCard response={response()} compact />);

    expect(screen.getByRole("button", { name: "Resources" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Helpful response" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not helpful response" })).toBeInTheDocument();
  });

  it("keeps sources collapsed until the Resources button is clicked", () => {
    render(<ResponseCard response={response(true)} compact />);

    const resources = screen.getByRole("button", { name: "Resources" });
    expect(resources).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("CortexAI documentation")).not.toBeInTheDocument();

    fireEvent.click(resources);

    expect(resources).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("CortexAI documentation")).toBeInTheDocument();
  });

  it("replaces the loading state as soon as streamed text arrives", () => {
    const pending = response(false, "");
    const { rerender } = render(
      <ResponseCard response={pending} isStreaming loadingMode="ask" />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Thinking through your request\u2026",
    );
    expect(screen.queryByText("Waiting for response...")).not.toBeInTheDocument();

    rerender(
      <ResponseCard
        response={{ ...pending, text: "The first streamed token" }}
        isStreaming
        loadingMode="ask"
      />,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("The first streamed token")).toBeInTheDocument();
  });

  it("uses request-aware loading copy for sources and prompt improvement", () => {
    const pending = response(false, "");
    const { rerender } = render(
      <ResponseCard
        response={pending}
        isStreaming
        loadingMode="compare"
        researchEnabled
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking sources and preparing an answer\u2026",
    );

    rerender(
      <ResponseCard
        response={pending}
        isStreaming
        loadingMode="compare"
        researchEnabled
        optimizeEnabled
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Refining prompt and preparing response\u2026",
    );
  });

  it("renders GFM tables with semantic headers and mobile data labels", () => {
    render(
      <ResponseCard
        response={response(
          false,
          [
            "| Area | Risk | Owner |",
            "| :--- | :---: | ---: |",
            "| API | Medium | Platform |",
            "| UI | Low | Product |",
          ].join("\n"),
        )}
      />,
    );

    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
    expect(screen.getByRole("columnheader", { name: "Risk" })).toHaveStyle({
      textAlign: "center",
    });
    expect(screen.getByRole("cell", { name: "Platform" })).toHaveAttribute(
      "data-label",
      "Owner",
    );
    expect(screen.getByRole("region", { name: "Response table" })).toHaveAttribute(
      "tabindex",
      "0",
    );
  });
});

function response(withSources = false, text = "A compact comparison response."): ChatResponse {
  return {
    request_id: "response-1",
    session_id: "session-1",
    text,
    provider: "claude",
    model: "claude-sonnet-4-5",
    latency_ms: 320,
    token_usage: {
      prompt_tokens: 20,
      completion_tokens: 40,
      total_tokens: 60,
    },
    estimated_cost: 0.001,
    cost_currency: "USD",
    web_source_items: withSources
      ? [{ title: "CortexAI documentation", url: "https://example.com/cortex" }]
      : [],
    timestamp: "2026-06-09T00:00:00.000Z",
  };
}
