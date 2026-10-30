import React, { type ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

import { PluginProvider, usePluginContext } from "@/core/plugins/context";

vi.mock("@/core/auth/tokens", () => ({
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

describe("plugin context callApi", () => {
  // callApi uses raw fetch(url, init), so the headers are in the second argument.
  function sentHeaders(spy: ReturnType<typeof mockFetch>): Headers {
    const init = spy.mock.calls.at(-1)?.[1] as RequestInit;
    return new Headers(init.headers);
  }

  it("sends the bearer token", async () => {
    const spy = mockFetch([]);
    const { result } = renderHook(() => usePluginContext(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await result.current.createPluginContext("slack").callApi("logs");

    expect(sentHeaders(spy).get("authorization")).toBe("Bearer test-token");
  });

  it("sends no authorization header without a token", async () => {
    const spy = mockFetch({});
    const { result } = renderHook(() => usePluginContext(), {
      wrapper: ({ children }: { children: ReactNode }) =>
        React.createElement(PluginProvider, { token: null, children }),
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await result.current.createPluginContext("slack").callApi("logs");

    expect(sentHeaders(spy).has("authorization")).toBe(false);
  });
});
