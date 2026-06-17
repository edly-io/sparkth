import React, { type ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

import { PluginProvider, usePluginContext } from "@/lib/plugins/context";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

function mockFetch(body: unknown, status = 200) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async () => new Response(JSON.stringify(body), { status }));
}

function sentRequests(spy: ReturnType<typeof mockFetch>): Request[] {
  return spy.mock.calls.map((call) => call[0] as Request);
}

function wrapper({ children }: { children: ReactNode }) {
  return React.createElement(PluginProvider, { token: "test-token", children });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("PluginProvider api calls", () => {
  it("GETs /api/v1/user-plugins/ with the bearer token on mount", async () => {
    const spy = mockFetch([]);

    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    const request = sentRequests(spy)[0];
    expect(new URL(request.url).pathname).toBe("/api/v1/user-plugins/");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
  });

  it("enablePlugin PATCHes the enable endpoint", async () => {
    const spy = mockFetch([]);

    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(() => result.current.enablePlugin("chat"));

    const request = sentRequests(spy).find((r) => new URL(r.url).pathname.endsWith("/chat/enable"));
    expect(request).toBeDefined();
    expect(new URL(request!.url).pathname).toBe("/api/v1/user-plugins/chat/enable");
    expect(request!.method).toBe("PATCH");
    expect(request!.headers.get("authorization")).toBe("Bearer test-token");
  });

  it("disablePlugin PATCHes the disable endpoint", async () => {
    const spy = mockFetch([]);

    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(() => result.current.disablePlugin("chat"));

    const request = sentRequests(spy).find((r) =>
      new URL(r.url).pathname.endsWith("/chat/disable"),
    );
    expect(request).toBeDefined();
    expect(request!.method).toBe("PATCH");
  });

  it("updatePluginConfig PUTs the merged config", async () => {
    const spy = mockFetch([]);

    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(() => result.current.updatePluginConfig("chat", { key: "v" }));

    const request = sentRequests(spy).find((r) => new URL(r.url).pathname.endsWith("/chat/config"));
    expect(request).toBeDefined();
    expect(new URL(request!.url).pathname).toBe("/api/v1/user-plugins/chat/config");
    expect(request!.method).toBe("PUT");
    await expect(request!.clone().json()).resolves.toEqual({ config: { key: "v" } });
  });

  it("surfaces the backend detail when the mount fetch fails", async () => {
    mockFetch({ detail: "Forbidden" }, 403);

    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Failed to fetch plugins: Forbidden");
  });
});
