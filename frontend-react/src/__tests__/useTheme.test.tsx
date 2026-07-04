import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { useTheme } from "../hooks/useTheme";

describe("useTheme", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.removeItem("cortex-theme");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.style.colorScheme = "";
  });

  it("applies and persists the selected dark theme", async () => {
    const user = userEvent.setup();
    render(<ThemeProbe />);

    expect(screen.getByRole("button", { name: "Current theme: light" })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(window.localStorage.getItem("cortex-theme")).toBe("light");

    await user.click(screen.getByRole("button", { name: "Current theme: light" }));

    expect(screen.getByRole("button", { name: "Current theme: dark" })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(window.localStorage.getItem("cortex-theme")).toBe("dark");
  });

  it("starts from a saved theme preference", () => {
    window.localStorage.setItem("cortex-theme", "dark");

    render(<ThemeProbe />);

    expect(screen.getByRole("button", { name: "Current theme: dark" })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });
});

function ThemeProbe() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button type="button" onClick={toggleTheme}>
      Current theme: {theme}
    </button>
  );
}
