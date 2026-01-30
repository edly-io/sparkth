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
      <Button variant="ghost" size="icon" disabled>
        <span className="w-5 h-5" />
      </Button>
    );
  }

  const Icon = theme === "dark" ? Moon : Sun;

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleTheme}
    >
      <Icon className="w-5 h-5" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  );
}
