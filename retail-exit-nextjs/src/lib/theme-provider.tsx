"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { Sun, Moon, Laptop } from "lucide-react";

export type Theme = "system" | "dark" | "light";

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: "dark" | "light";
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "system",
  resolvedTheme: "dark",
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("secops_theme") as Theme) || "system";
    }
    return "system";
  });
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const media = window.matchMedia("(prefers-color-scheme: dark)");

    const applyTheme = () => {
      let active: "dark" | "light" = "dark";
      if (theme === "system") {
        active = media.matches ? "dark" : "light";
      } else {
        active = theme;
      }

      setResolvedTheme(active);

      const root = document.documentElement;
      root.classList.remove("dark", "light");
      root.classList.add(active);
      root.setAttribute("data-theme", active);
      localStorage.setItem("secops_theme", theme);
    };

    applyTheme();

    const listener = () => {
      if (theme === "system") applyTheme();
    };

    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [theme, mounted]);

  const setTheme = (t: Theme) => {
    setThemeState(t);
  };

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-0.5 text-xs font-mono shadow-sm">
      <button
        onClick={() => setTheme("light")}
        title="Light Mode"
        className={`flex items-center gap-1 px-2 py-1 rounded transition-all ${
          theme === "light"
            ? "bg-[var(--bg-panel-raised)] text-[var(--signal-amber)] font-bold shadow-sm"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        <Sun size={13} />
        <span className="hidden xl:inline text-[11px]">Light</span>
      </button>

      <button
        onClick={() => setTheme("dark")}
        title="Dark Mode"
        className={`flex items-center gap-1 px-2 py-1 rounded transition-all ${
          theme === "dark"
            ? "bg-[var(--bg-panel-raised)] text-[var(--status-ok)] font-bold shadow-sm"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        <Moon size={13} />
        <span className="hidden xl:inline text-[11px]">Dark</span>
      </button>

      <button
        onClick={() => setTheme("system")}
        title="System Auto Mode"
        className={`flex items-center gap-1 px-2 py-1 rounded transition-all ${
          theme === "system"
            ? "bg-[var(--bg-panel-raised)] text-[#38BDF8] font-bold shadow-sm"
            : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        }`}
      >
        <Laptop size={13} />
        <span className="hidden xl:inline text-[11px]">Auto</span>
      </button>
    </div>
  );
}
