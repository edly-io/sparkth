"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/Button";
import { Moon, Sun } from "lucide-react";

const emptySubscribe = () => () => {};

function useHasMounted() {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );
}

export function ThemeToggle() {
  const mounted = useHasMounted();
  const { theme, toggleTheme } = useTheme();

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" className="w-9 h-9" disabled>
        <span className="w-4 h-4" />
      </Button>
    );
  }

  const Icon = theme === "dark" ? Moon : Sun;

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleTheme}
      className="w-9 h-9"
    >
      <Icon className="w-4 h-4" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  );
}
