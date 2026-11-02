import { useTheme as useNextTheme } from "next-themes";

/** The current theme, light until it is resolved, and functions to set or toggle it. */
export function useTheme() {
  const { setTheme, resolvedTheme } = useNextTheme();

  return {
    theme: (resolvedTheme ?? "light") as "light" | "dark",
    setTheme: (newTheme: "light" | "dark") => setTheme(newTheme),
    toggleTheme: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
  };
}
