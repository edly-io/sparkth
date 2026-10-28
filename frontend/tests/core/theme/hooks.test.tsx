import { beforeEach, describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useTheme } from "@/core/theme/hooks";

const nextThemes = vi.hoisted(() => ({
  setTheme: vi.fn(),
  resolvedTheme: undefined as string | undefined,
}));

vi.mock("next-themes", () => ({
  useTheme: () => nextThemes,
}));

describe("useTheme", () => {
  beforeEach(() => {
    nextThemes.setTheme.mockReset();
    nextThemes.resolvedTheme = undefined;
  });

  it("reports light until the theme is resolved", () => {
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe("light");
  });

  it("toggles dark to light and light to dark", () => {
    nextThemes.resolvedTheme = "dark";
    const { result, rerender } = renderHook(() => useTheme());

    result.current.toggleTheme();
    expect(nextThemes.setTheme).toHaveBeenLastCalledWith("light");

    nextThemes.resolvedTheme = "light";
    rerender();
    result.current.toggleTheme();
    expect(nextThemes.setTheme).toHaveBeenLastCalledWith("dark");
  });
});
