import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { registerPlugin, unregisterPlugin } from "@/core/plugins/registry";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

describe("useIsPluginEnabled", () => {
  afterEach(() => {
    unregisterPlugin("example");
    vi.restoreAllMocks();
  });

  it("reports a plugin registered with core and enabled for the user", async () => {
    registerPlugin({ name: "example", loadComponent: async () => ({ default: () => null }) });
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response(JSON.stringify([{ plugin_name: "example", enabled: true }])),
    );

    const { result } = renderHook(() => useIsPluginEnabled("test-token", "example"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isEnabled).toBe(true);
  });
});
