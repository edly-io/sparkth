import { afterEach, describe, it, expect, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import {
  HISTORY_COLLAPSED_KEY,
  useHistoryCollapsed,
} from "@/plugins/compose/hooks/useHistoryCollapsed";

describe("useHistoryCollapsed", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("starts expanded when nothing is stored", async () => {
    const { result } = renderHook(() => useHistoryCollapsed());

    await waitFor(() => expect(result.current[0]).toBe(false));
  });

  it("restores a stored collapsed flag after mount", async () => {
    localStorage.setItem(HISTORY_COLLAPSED_KEY, "true");

    const { result } = renderHook(() => useHistoryCollapsed());

    await waitFor(() => expect(result.current[0]).toBe(true));
  });

  it("stores the flag when it changes", () => {
    const { result } = renderHook(() => useHistoryCollapsed());

    act(() => result.current[1](true));

    expect(localStorage.getItem(HISTORY_COLLAPSED_KEY)).toBe("true");
    expect(result.current[0]).toBe(true);
  });

  it("keeps working when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    const { result } = renderHook(() => useHistoryCollapsed());
    await waitFor(() => expect(result.current[0]).toBe(false));

    act(() => result.current[1](true));

    expect(result.current[0]).toBe(true);
  });
});
