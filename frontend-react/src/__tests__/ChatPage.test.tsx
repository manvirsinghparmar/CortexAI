import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPage } from "../pages/ChatPage";
import { useChatStore } from "../store/chatStore";
import type { CognitoConfig, WhoAmIResponse } from "../types";

interface MockAuthState {
  whoAmI: WhoAmIResponse | null;
  cognitoConfig: CognitoConfig | null;
  loading: boolean;
  loggedIn: boolean;
}

const mocks = vi.hoisted(() => ({
  authState: {
    whoAmI: null,
    cognitoConfig: { enabled: true, domain: "https://auth.example.com", clientId: "client-123" },
    loading: false,
    loggedIn: false,
  } satisfies MockAuthState,
  login: vi.fn(),
  logout: vi.fn(),
  loadHistory: vi.fn(),
  removeThread: vi.fn(),
  submit: vi.fn(),
  regenerate: vi.fn(),
  cancel: vi.fn(),
  useModels: vi.fn(),
}));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    ...mocks.authState,
    login: mocks.login,
    logout: mocks.logout,
    refresh: vi.fn(),
  }),
}));

vi.mock("../hooks/useModels", () => ({
  useModels: mocks.useModels,
}));

vi.mock("../hooks/useHistory", () => ({
  useHistory: () => ({
    load: mocks.loadHistory,
    removeThread: mocks.removeThread,
    clear: vi.fn(),
  }),
}));

vi.mock("../hooks/useChat", () => ({
  useChat: () => ({
    submit: mocks.submit,
    cancel: mocks.cancel,
    regenerate: mocks.regenerate,
  }),
}));

vi.mock("../components/composer/PromptComposer", () => ({
  PromptComposer: () => <div data-testid="prompt-composer" />,
}));

vi.mock("../components/results/ResultsSection", () => ({
  ResultsSection: () => <div data-testid="results-section" />,
}));

vi.mock("../components/shared/ExampleChips", () => ({
  ExampleChips: () => <div data-testid="example-chips" />,
}));

describe("ChatPage authentication gate", () => {
  beforeEach(() => {
    Object.assign(mocks.authState, {
      whoAmI: null,
      cognitoConfig: {
        enabled: true,
        domain: "https://auth.example.com",
        clientId: "client-123",
      },
      loading: false,
      loggedIn: false,
    });
    mocks.useModels.mockReturnValue({ models: [], loading: false, error: null });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    resetStore();
  });

  it("shows a sign-in gate instead of the workspace for signed-out Cognito users", async () => {
    const user = userEvent.setup();

    renderChatPage();

    const signInRegion = screen.getByRole("region", { name: "Sign in to use CortexAI" });
    expect(signInRegion).toBeInTheDocument();
    expect(signInRegion).toHaveTextContent(
      "Access your AI workspace, saved chats, model comparison, and file analysis.",
    );
    expect(screen.queryByText(/Backend not connected/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/port 8000/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("prompt-composer")).not.toBeInTheDocument();
    expect(screen.queryByTestId("example-chips")).not.toBeInTheDocument();
    expect(screen.getByText("Sign in to view history.")).toBeInTheDocument();
    expect(mocks.useModels).toHaveBeenCalledWith(false);
    expect(mocks.loadHistory).not.toHaveBeenCalled();

    await user.click(within(signInRegion).getByRole("button", { name: "Sign in" }));

    expect(mocks.login).toHaveBeenCalledTimes(1);
  });

  it("renders the workspace and startup fetches once the session is authenticated", async () => {
    Object.assign(mocks.authState, {
      whoAmI: whoAmI(),
      cognitoConfig: {
        enabled: true,
        domain: "https://auth.example.com",
        clientId: "client-123",
      },
      loading: false,
      loggedIn: true,
    });

    renderChatPage();

    expect(screen.queryByRole("region", { name: "Sign in to use CortexAI" })).not.toBeInTheDocument();
    expect(screen.getByTestId("prompt-composer")).toBeInTheDocument();
    expect(screen.getByTestId("example-chips")).toBeInTheDocument();
    expect(mocks.useModels).toHaveBeenCalledWith(true);
    await waitFor(() => {
      expect(mocks.loadHistory).toHaveBeenCalledWith({ restoreActiveTranscript: true });
    });
  });

  it("retries the latest failed turn through regeneration", async () => {
    Object.assign(mocks.authState, {
      whoAmI: whoAmI(),
      cognitoConfig: { enabled: false },
      loading: false,
      loggedIn: true,
    });
    const turnId = useChatStore.getState().beginTurn({
      mode: "single",
      prompt: "Retry this prompt",
      submittedPrompt: "Retry this prompt",
      attachments: [],
      responses: [],
      status: "error",
    });
    useChatStore.getState().setError("Temporary upstream outage");
    const user = userEvent.setup();

    renderChatPage();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(mocks.regenerate).toHaveBeenCalledWith(turnId);
    expect(mocks.submit).not.toHaveBeenCalled();
  });
});

function renderChatPage() {
  render(
    <BrowserRouter>
      <ChatPage />
    </BrowserRouter>,
  );
}

function resetStore() {
  useChatStore.getState().startNewChat();
  useChatStore.getState().setHistory([]);
  useChatStore.getState().setHistorySearch("");
  useChatStore.getState().setMode("single");
}

function whoAmI() {
  return {
    api_key_id: "test-key",
    user_id: "signed-in-user",
    plan_tier: "Pro",
    storage_policy: "full",
    redact_pii: false,
    baseline: {
      provider: "openai",
      model: "gpt-5.1",
      source: "test",
    },
    rate_limits: {
      requests_per_minute: 60,
      daily_cap_scope: "user",
    },
    breakers: {
      failure_threshold: 5,
      window_seconds: 60,
      cooldown_seconds: 120,
      scope: "provider_model",
    },
  };
}
