import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggle: () => void;
  // colors for charts (Recharts needs explicit values, not CSS vars)
  grid: string;
  axis: string;
}

const ThemeContext = createContext<ThemeContextValue>(null!);

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}

function initialTheme(): Theme {
  const saved = localStorage.getItem("ft_theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("ft_theme", theme);
  }, [theme]);

  const value: ThemeContextValue = {
    theme,
    toggle: () => setTheme((t) => (t === "light" ? "dark" : "light")),
    grid: theme === "dark" ? "#272b38" : "#ecedf3",
    axis: theme === "dark" ? "#99a0b1" : "#98a0b3",
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
