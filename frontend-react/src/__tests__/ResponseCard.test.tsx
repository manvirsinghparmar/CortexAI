import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResponseCard } from "../components/results/ResponseCard";
import type { ChatResponse } from "../types";

describe("ResponseCard", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

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

    expect(screen.queryByRole("button", { name: "Resources" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy response" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Helpful response" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not helpful response" })).toBeInTheDocument();
  });

  it("keeps response stats collapsed behind the integrated run-details control", () => {
    render(<ResponseCard response={response()} compact />);

    const details = screen.getByRole("button", { name: "Show run details" });
    const stats = document.getElementById(details.getAttribute("aria-controls") ?? "");

    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(details).not.toHaveTextContent("Details");
    expect(stats?.className).not.toContain("metaRowExpanded");

    fireEvent.click(details);

    expect(details).toHaveAttribute("aria-expanded", "true");
    expect(details).toHaveAccessibleName("Hide run details");
    expect(stats?.className).toContain("metaRowExpanded");
    expect(stats).toHaveTextContent("20.0 sec");
    expect(stats).toHaveTextContent("60 tokens");
    expect(stats).toHaveTextContent("$0.00100");
    expect(stats?.querySelectorAll("svg")).toHaveLength(3);
  });

  it("shows live elapsed loading meta without placeholder zero metrics", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-09T00:00:08.000Z"));
    const pending = {
      ...response(false, ""),
      latency_ms: null,
      token_usage: null,
      estimated_cost: 0,
      ui_status: "streaming" as const,
      started_at: "2026-06-09T00:00:00.000Z",
    };

    render(<ResponseCard response={pending} isStreaming loadingMode="compare" />);

    const header = document.querySelector("header");
    const stats = header?.querySelector('[id^="response-stats-"]');
    expect(screen.queryByRole("button", { name: /run details/i })).not.toBeInTheDocument();
    expect(stats?.className).toContain("metaRowPinned");
    expect(stats?.className).toContain("loadingMetaRow");
    expect(header?.firstElementChild?.nextElementSibling).toBe(stats);
    expect(header).toHaveTextContent("00:08 elapsed · Generating response");
    expect(header).not.toHaveTextContent("0.00 sec");
    expect(header).not.toHaveTextContent("0 tokens");

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(header).toHaveTextContent("00:10 elapsed · Generating response");
  });

  it("formats completed metrics with duration and grouped token count", () => {
    const completed = {
      ...response(false, "Completed answer."),
      latency_ms: 12400,
      token_usage: {
        prompt_tokens: 248,
        completion_tokens: 1000,
        total_tokens: 1248,
      },
      estimated_cost: 0,
    };

    render(<ResponseCard response={completed} compact />);

    const header = document.querySelector("header");
    expect(header).toHaveTextContent("12.4 sec");
    expect(header).toHaveTextContent("1,248 tokens");
    expect(header?.querySelectorAll("svg")).toHaveLength(2);
    expect(header).not.toHaveTextContent("1.2k");
  });

  it("uses UI-observed timestamps for completed duration when available", () => {
    const completed = {
      ...response(false, "Completed answer."),
      latency_ms: 1200,
      started_at: "2026-06-09T00:00:00.000Z",
      completed_at: "2026-06-09T00:00:08.400Z",
      estimated_cost: 0,
    };

    render(<ResponseCard response={completed} compact />);

    const header = document.querySelector("header");
    expect(header).toHaveTextContent("8.4 sec");
    expect(header).not.toHaveTextContent("1.2 sec");
  });

  it("hides the token metric when completed token usage is unavailable", () => {
    const completed = {
      ...response(false, "Completed answer."),
      token_usage: null,
      estimated_cost: 0,
    };

    render(<ResponseCard response={completed} compact />);

    const header = document.querySelector("header");
    expect(header).toHaveTextContent("20.0 sec");
    expect(header).not.toHaveTextContent("tokens");
  });

  it("shows failed elapsed time without token metrics", () => {
    const failed = {
      ...response(false, ""),
      latency_ms: null,
      token_usage: null,
      estimated_cost: 0,
      ui_status: "failed" as const,
      started_at: "2026-06-09T00:00:00.000Z",
      failed_at: "2026-06-09T00:00:08.200Z",
      error: {
        code: "stream_error",
        message: "Stream disconnected.",
        provider: "claude",
        retryable: false,
        details: {},
      },
    };

    render(<ResponseCard response={failed} compact />);

    const header = document.querySelector("header");
    expect(header).toHaveTextContent("Failed after 8.2 sec");
    expect(header).not.toHaveTextContent("tokens");
  });

  it("does not render legacy source controls when sources have no inline markers", () => {
    render(<ResponseCard response={response(true, "A sourced answer without inline refs.")} compact />);

    expect(screen.queryByRole("button", { name: "Resources" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /source:/i })).not.toBeInTheDocument();
    expect(screen.queryByText("CortexAI documentation")).not.toBeInTheDocument();
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

  it("groups consecutive numeric citations into one publisher pill", () => {
    render(
      <ResponseCard
        response={responseWithSources("The claim is supported. [1][2] [3]")}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Sources: NPR and 2 more" }),
    ).toHaveTextContent("NPR + 2");
  });

  it("does not convert citation-looking text inside links or code", () => {
    const { container } = render(
      <ResponseCard
        response={response(
          false,
          [
            "Read [the source](https://example.com/path).",
            "",
            "Inline `value [1]` remains code.",
            "",
            "```txt",
            "block [2]",
            "```",
          ].join("\n"),
        )}
      />,
    );

    expect(container.querySelector("cite")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /source:/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "the source" })).toHaveAttribute(
      "href",
      "https://example.com/path",
    );
    expect(screen.getByText("value [1]")).toBeInTheDocument();
    expect(screen.getByText("block [2]")).toBeInTheDocument();
  });

  it("opens citation previews with source links and closes them from keyboard or outside clicks", () => {
    render(<ResponseCard response={responseWithSources("Supported by reporting. [1][2]")} />);

    const pill = screen.getByRole("button", { name: "Sources: NPR and 1 more" });
    fireEvent.click(pill);

    const dialog = screen.getByRole("dialog", { name: "Citation sources" });
    expect(dialog).toBeInTheDocument();
    expect(
      within(dialog).getByRole("link", { name: /Morning Edition NPR/ }),
    ).toHaveAttribute("href", "https://www.npr.org/sections/news/");
    expect(
      within(dialog).getByRole("link", { name: /World report BBC/ }),
    ).toHaveAttribute("href", "https://www.bbc.co.uk/news/world");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Citation sources" })).not.toBeInTheDocument();

    fireEvent.click(pill);
    expect(screen.getByRole("dialog", { name: "Citation sources" })).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog", { name: "Citation sources" })).not.toBeInTheDocument();
  });

  it("opens the citation external icon as a direct source link", () => {
    render(<ResponseCard response={responseWithSources("Supported by reporting. [1]")} />);

    expect(
      screen.getByRole("link", { name: "Open NPR source in a new tab" }),
    ).toHaveAttribute("href", "https://www.npr.org/sections/news/");
  });

  it("normalizes source links that arrive without a URL scheme", () => {
    render(
      <ResponseCard
        response={{
          ...response(false, "Supported by reporting. [1]"),
          web_source_items: [
            { title: "Bare source", url: "example.com/report" },
          ],
        }}
      />,
    );

    expect(
      screen.getByRole("link", { name: "Open Example source in a new tab" }),
    ).toHaveAttribute("href", "https://example.com/report");

    fireEvent.click(screen.getByRole("button", { name: "Source: Example" }));
    expect(
      within(screen.getByRole("dialog", { name: "Citation sources" })).getByRole(
        "link",
        { name: /Bare source/ },
      ),
    ).toHaveAttribute("href", "https://example.com/report");
  });

  it("falls back to a publisher initial when a citation favicon fails", () => {
    render(<ResponseCard response={responseWithSources("Supported by reporting. [1]")} />);

    fireEvent.click(screen.getByRole("button", { name: "Source: NPR" }));

    const dialog = screen.getByRole("dialog", { name: "Citation sources" });
    const favicon = dialog.querySelector("img");
    expect(favicon).not.toBeNull();
    fireEvent.error(favicon!);

    expect(within(dialog).getByText("N")).toBeInTheDocument();
  });

  it("uses a bottom-sheet citation preview on phone-sized screens", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(max-width: 760px)",
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    try {
      render(<ResponseCard response={responseWithSources("Supported by reporting. [1]")} />);

      fireEvent.click(screen.getByRole("button", { name: "Source: NPR" }));

      expect(screen.getByRole("dialog", { name: "Citation sources" }).className).toContain(
        "citationSheet",
      );
    } finally {
      window.matchMedia = originalMatchMedia;
    }
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
    latency_ms: 20027,
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

function responseWithSources(text: string): ChatResponse {
  return {
    ...response(false, text),
    web_source_items: [
      { title: "Morning Edition", url: "https://www.npr.org/sections/news/" },
      { title: "World report", url: "https://www.bbc.co.uk/news/world" },
      { title: "Large language model - Wikipedia", url: "https://en.wikipedia.org/wiki/Large_language_model" },
    ],
  };
}
