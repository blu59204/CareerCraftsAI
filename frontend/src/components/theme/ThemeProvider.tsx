"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Theme = "light" | "dark";
export type Zone = "marketing" | "app";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = "theme";

function readSaved(): Theme | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage?.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({
  children,
  zoneDefault,
}: {
  children: React.ReactNode;
  zoneDefault: Theme;
}) {
  const [theme, setThemeState] = useState<Theme>(zoneDefault);

  useEffect(() => {
    const saved = readSaved();
    const initial: Theme = saved ?? zoneDefault ?? systemTheme();
    setThemeState(initial);
  }, [zoneDefault]);

  useEffect(() => {
    try {
      window.localStorage?.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage can be unavailable in embedded browser contexts.
    }
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(theme);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const domTheme: Theme = document.documentElement.classList.contains("dark") ? "dark" : "light";
      return (current === "dark" || domTheme === "dark") ? "light" : "dark";
    });
  }, []);

  const value = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme, setTheme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}
