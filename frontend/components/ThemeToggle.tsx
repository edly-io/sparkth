"use client";

import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/Button";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setTheme("light")}
        className={
          theme === "light" ? "bg-neutral-100 dark:bg-neutral-800" : ""
        }
      >
        ☀️
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setTheme("dark")}
        className={theme === "dark" ? "bg-neutral-100 dark:bg-neutral-800" : ""}
      >
        🌙
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setTheme("system")}
        className={
          theme === "system" ? "bg-neutral-100 dark:bg-neutral-800" : ""
        }
      >
        💻
      </Button>
    </div>
  );
}
