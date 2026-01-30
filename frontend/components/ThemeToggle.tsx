"use client";

import { useEffect, useState } from "react";
import { useTheme } from "@/lib/ThemeContext";
import { Button } from "@/components/ui/Button";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" className="w-9 h-9">
        <span className="sr-only">Toggle theme</span>
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
