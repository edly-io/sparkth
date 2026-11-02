import { afterEach, describe, it, expect, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { SidebarProvider } from "@/core/sidebar/context";
import { useSidebar } from "@/core/sidebar/hooks";

describe("useSidebar", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("throws when used outside a SidebarProvider", () => {
    // React reports the render error to console.error; keep the test output clean.
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useSidebar())).toThrow(
      "useSidebar must be used within a SidebarProvider",
    );
  });

  it("opens, closes and toggles the mobile sidebar", () => {
    const { result } = renderHook(() => useSidebar(), { wrapper: SidebarProvider });
    expect(result.current.isOpen).toBe(false);

    act(() => result.current.open());
    expect(result.current.isOpen).toBe(true);

    act(() => result.current.close());
    expect(result.current.isOpen).toBe(false);

    act(() => result.current.toggle());
    expect(result.current.isOpen).toBe(true);
  });

  it("collapses and expands the desktop sidebar", () => {
    const { result } = renderHook(() => useSidebar(), { wrapper: SidebarProvider });
    expect(result.current.isCollapsed).toBe(false);

    act(() => result.current.toggleCollapsed());
    expect(result.current.isCollapsed).toBe(true);

    act(() => result.current.setCollapsed(false));
    expect(result.current.isCollapsed).toBe(false);
  });
});
