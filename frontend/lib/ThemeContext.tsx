"use client";

import {
  ThemeProvider as NextThemesProvider,
  useTheme as useNextTheme,
} from "next-themes";
import { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}

export function useTheme() {
  const { setTheme, resolvedTheme } = useNextTheme();

  return {
    theme: (resolvedTheme ?? "light") as "light" | "dark",
    setTheme: (newTheme: "light" | "dark") => setTheme(newTheme),
    toggleTheme: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
  };
}
