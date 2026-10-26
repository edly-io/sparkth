import type { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { PluginProvider } from "@/core/plugins/context";
import { usePlugin } from "@/lib/plugins/context";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

function wrapper({ children }: { children: ReactNode }) {
  return <PluginProvider token="test-token">{children}</PluginProvider>;
}

describe("usePlugin", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reads the plugin's state from core's PluginProvider", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          JSON.stringify([{ plugin_name: "example", enabled: true, config: { limit: 3 } }]),
        ),
    );

    const { result } = renderHook(() => usePlugin("example"), { wrapper });

    await waitFor(() => expect(result.current.isEnabled).toBe(true));
    expect(result.current.config).toEqual({ limit: 3 });
  });
});
