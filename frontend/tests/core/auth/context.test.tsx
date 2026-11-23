import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/core/auth/context";
import { LOGOUT_HANDLERS } from "@/lib/auth/slots";
import { useAuth } from "@/lib/auth/hooks";

describe("AuthProvider — logging out", () => {
  afterEach(() => LOGOUT_HANDLERS.delete("exampleplugin"));

  it("runs every plugin's logout handler", async () => {
    const clearExample = vi.fn();
    LOGOUT_HANDLERS.set("exampleplugin", [clearExample]);
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.logout());

    expect(clearExample).toHaveBeenCalledOnce();
  });
});
