import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountMenu } from "../components/layout/AccountMenu";

describe("AccountMenu", () => {
  afterEach(() => {
    cleanup();
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
