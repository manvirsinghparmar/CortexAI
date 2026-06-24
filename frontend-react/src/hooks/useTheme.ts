import { useEffect, useState } from "react";

export type AppTheme = "light" | "dark";

const STORAGE_KEY = "cortex-theme";

function readInitialTheme(): AppTheme {
  if (typeof window === "undefined") return "light";

  try {
    const storedTheme = window.localStorage.getItem(STORAGE_KEY);
    if (storedTheme === "dark" || storedTheme === "light") return storedTheme;
  } catch {
    // Fall back to any theme already applied to the page.
  }

  if (typeof document !== "undefined") {
    const documentTheme = document.documentElement.getAttribute("data-theme");
    if (documentTheme === "dark" || documentTheme === "light") return documentTheme;
  }

  return "light";
}

export function useTheme() {
  const [theme, setTheme] = useState<AppTheme>(() => readInitialTheme());

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme;

    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Theme still applies for the current page when storage is unavailable.
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  };

  return { theme, toggleTheme };
}
