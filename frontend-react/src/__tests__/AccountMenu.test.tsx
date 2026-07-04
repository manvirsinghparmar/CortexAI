import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountMenu } from "../components/layout/AccountMenu";

describe("AccountMenu", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows Log off from the account icon for signed-in Cognito users", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();

    render(<AccountMenu authEnabled loggedIn onLogout={onLogout} />);

    const accountButton = screen.getByRole("button", { name: "Account" });
    expect(accountButton).toHaveAttribute("aria-haspopup", "menu");
    expect(accountButton).toHaveAttribute("aria-expanded", "false");

    await user.click(accountButton);

    expect(accountButton).toHaveAttribute("aria-expanded", "true");
    const menu = screen.getByRole("menu", { name: "Account menu" });
    const logOff = screen.getByRole("menuitem", { name: "Log off" });
    expect(menu).toContainElement(logOff);

    await user.click(logOff);

    expect(onLogout).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
  });

  it("opens on hover and closes on Escape", async () => {
    const user = userEvent.setup();

    render(<AccountMenu authEnabled loggedIn onLogout={vi.fn()} />);

    fireEvent.mouseEnter(screen.getByRole("button", { name: "Account" }).parentElement!);
    expect(screen.getByRole("menuitem", { name: "Log off" })).toBeInTheDocument();

    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(screen.queryByRole("menuitem", { name: "Log off" })).not.toBeInTheDocument();
    });
  });

  it("keeps the menu open while moving from the account icon to the submenu", () => {
    vi.useFakeTimers();
    render(<AccountMenu authEnabled loggedIn onLogout={vi.fn()} />);

    const root = screen.getByRole("button", { name: "Account" }).parentElement!;
    fireEvent.mouseEnter(root);

    const menu = screen.getByRole("menu", { name: "Account menu" });
    expect(screen.getByRole("menuitem", { name: "Log off" })).toBeInTheDocument();

    fireEvent.mouseLeave(root, { relatedTarget: document.body });
    expect(screen.getByRole("menu", { name: "Account menu" })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(80);
    });
    fireEvent.mouseEnter(menu);
    act(() => {
      vi.advanceTimersByTime(180);
    });

    expect(screen.getByRole("menu", { name: "Account menu" })).toBeInTheDocument();

    fireEvent.mouseLeave(root, { relatedTarget: document.body });
    act(() => {
      vi.advanceTimersByTime(180);
    });

    expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
  });

  it("shows Sign in for Cognito guests", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn();

    render(<AccountMenu authEnabled={true} loggedIn={false} onLogin={onLogin} />);

    const accountButton = screen.getByRole("button", { name: "Guest account" });
    await user.click(accountButton);
    expect(screen.getByRole("menuitem", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Log off" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: "Sign in" }));
    expect(onLogin).toHaveBeenCalledTimes(1);
  });

  it("keeps Log off available for guest account states when logout is wired", async () => {
    const user = userEvent.setup();
    const onLogin = vi.fn();
    const onLogout = vi.fn();

    render(
      <AccountMenu
        authEnabled={true}
        loggedIn={false}
        onLogin={onLogin}
        onLogout={onLogout}
      />,
    );

    const accountButton = screen.getByRole("button", { name: "Guest account" });
    await user.click(accountButton);

    expect(screen.getByRole("menuitem", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Log off" })).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: "Log off" }));
    expect(onLogout).toHaveBeenCalledTimes(1);
    expect(onLogin).not.toHaveBeenCalled();
  });

  it("shows the theme switch action inside the account menu", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    const onToggleTheme = vi.fn();

    render(
      <AccountMenu
        authEnabled
        loggedIn
        onLogout={onLogout}
        theme="light"
        onToggleTheme={onToggleTheme}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Account" }));

    const themeAction = screen.getByRole("menuitem", { name: "Switch to dark theme" });
    expect(themeAction).toHaveTextContent("Dark theme");
    expect(screen.getByRole("menuitem", { name: "Log off" })).toBeInTheDocument();

    await user.click(themeAction);

    expect(onToggleTheme).toHaveBeenCalledTimes(1);
    expect(onLogout).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
  });

  it("opens Usage & insights from the account menu when wired", async () => {
    const user = userEvent.setup();
    const onUsageInsights = vi.fn();

    render(
      <AccountMenu
        authEnabled={false}
        loggedIn={false}
        onUsageInsights={onUsageInsights}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Guest account" }));

    const usageAction = screen.getByRole("menuitem", { name: "Usage & insights" });
    expect(usageAction).toBeInTheDocument();

    await user.click(usageAction);
    expect(onUsageInsights).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu", { name: "Account menu" })).not.toBeInTheDocument();
  });

  it("updates the theme switch label for dark mode", async () => {
    const user = userEvent.setup();

    render(
      <AccountMenu
        authEnabled={false}
        loggedIn={false}
        theme="dark"
        onToggleTheme={vi.fn()}
      />,
    );

    const accountButton = screen.getByRole("button", { name: "Guest account" });
    expect(accountButton).toHaveAttribute("aria-haspopup", "menu");

    await user.click(accountButton);

    const themeAction = screen.getByRole("menuitem", { name: "Switch to light theme" });
    expect(themeAction).toHaveTextContent("Light theme");
    expect(screen.queryByRole("menuitem", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Log off" })).not.toBeInTheDocument();
  });

  it("shows Log off for guest account states when Cognito sign-in is unavailable", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();

    render(<AccountMenu authEnabled={false} loggedIn={false} onLogout={onLogout} />);

    const accountButton = screen.getByRole("button", { name: "Guest account" });
    await user.click(accountButton);

    const logOff = screen.getByRole("menuitem", { name: "Log off" });
    expect(logOff).toBeInTheDocument();

    await user.click(logOff);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("does not expose production auth menu actions when Cognito is disabled", async () => {
    const user = userEvent.setup();

    render(<AccountMenu authEnabled={false} loggedIn={false} onLogin={vi.fn()} />);

    const accountButton = screen.getByRole("button", { name: "Guest account" });
    expect(accountButton).not.toHaveAttribute("aria-haspopup");

    await user.click(accountButton);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Log off" })).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Sign in" })).not.toBeInTheDocument();
  });
});
