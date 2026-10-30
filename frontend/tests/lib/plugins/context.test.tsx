import type { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { PluginProvider, usePluginContext } from "@/core/plugins/context";
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

  it("reports loading until the user's plugins arrive", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response(JSON.stringify([{ plugin_name: "example", enabled: true }])),
    );

    const { result } = renderHook(() => usePlugin("example"), { wrapper });

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.isEnabled).toBe(true);
  });

  it("reports the plugin enabled once the user turns it on", async () => {
    let enabled = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if ((input as Request).method === "PATCH") {
        enabled = true;
        return new Response(JSON.stringify({ plugin_name: "example", enabled }));
      }
      return new Response(JSON.stringify([{ plugin_name: "example", enabled }]));
    });

    const { result } = renderHook(
      () => ({ plugin: usePlugin("example"), plugins: usePluginContext() }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.plugin.loading).toBe(false));
    expect(result.current.plugin.isEnabled).toBe(false);

    await result.current.plugins.enablePlugin("example");

    await waitFor(() => expect(result.current.plugin.isEnabled).toBe(true));
  });
});
