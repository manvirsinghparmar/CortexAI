import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModelsCatalogScreen, ModelsPage } from "../pages/ModelsPage";
import { useChatStore } from "../store/chatStore";

const hookMocks = vi.hoisted(() => ({
  loadHistory: vi.fn(),
  clearHistory: vi.fn(),
  removeThread: vi.fn(),
  cancel: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  toggleTheme: vi.fn(),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    whoAmI: null,
    cognitoConfig: { enabled: false },
    loading: false,
    loggedIn: false,
    login: hookMocks.login,
    logout: hookMocks.logout,
  }),
}));

vi.mock("../hooks/useHistory", () => ({
  useHistory: () => ({
    load: hookMocks.loadHistory,
    clear: hookMocks.clearHistory,
    removeThread: hookMocks.removeThread,
  }),
}));

vi.mock("../hooks/useChat", () => ({
  useChat: () => ({ cancel: hookMocks.cancel }),
}));

vi.mock("../hooks/useTheme", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: hookMocks.toggleTheme }),
}));

describe("ModelsPage", () => {
  beforeEach(() => {
    resetStore();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    resetStore();
  });

  it("renders the Models route with the compact task-first catalog", () => {
    renderPage();

    expect(screen.getAllByRole("heading", { name: "Models" }).length).toBeGreaterThan(0);
    expect(screen.getByText("22 of 22 models")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Models" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "Coding" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByLabelText("Smart routing hint")).toHaveTextContent("Smart routing");
    expect(screen.getByRole("button", { name: "GPT-5.4 details" })).toBeInTheDocument();
    expect(screen.getAllByRole("img", { name: "Speed: Medium" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("img", { name: "Depth: Deep" }).length).toBeGreaterThan(0);
  });

  it("filters by task and highlights the recommended row", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Coding" }));

    expect(screen.getByText("15 of 22 models")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Coding" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText("Best model for Coding")).toHaveTextContent(
      "Claude Sonnet 4.6",
    );
    const sonnetRow = screen
      .getByRole("button", { name: "Claude Sonnet 4.6 details" })
      .closest("article");
    expect(sonnetRow).not.toBeNull();
    expect(within(sonnetRow!).getByText("★ TOP")).toBeInTheDocument();
  });

  it("filters by search and exposes the no-match state with a clear action", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByRole("searchbox", { name: "Search models" }), "not-a-model");

    expect(screen.getByText("0 of 22 models")).toBeInTheDocument();
    expect(screen.getByText("No models match — clear filters")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(screen.getByText("22 of 22 models")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search models" })).toHaveValue("");
  });

  it("expands a compact model row to show tags, strengths, and the model id", async () => {
    const user = userEvent.setup();
    renderPage();

    const rowButton = screen.getByRole("button", { name: "GPT-5.2 Codex details" });
    expect(rowButton).toHaveAttribute("aria-expanded", "false");

    await user.click(rowButton);

    expect(rowButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("openai:gpt-5.2-codex")).toBeInTheDocument();
    expect(screen.getByText("Repo-scale context handling")).toBeInTheDocument();
    expect(screen.getAllByText("Long context").length).toBeGreaterThan(1);
  });

  it("renders the loading skeleton state for future async catalog loading", () => {
    render(<ModelsCatalogScreen loading />);

    expect(screen.getByLabelText("Loading models")).toHaveAttribute("aria-busy", "true");
  });
});

function renderPage() {
  render(
    <MemoryRouter>
      <ModelsPage />
    </MemoryRouter>,
  );
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}
