import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  disconnectSlack,
  fetchLogs,
  fetchRagSources,
  getAuthorizationUrl,
  getConnectionStatus,
} from "@/lib/slack-api";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

function mockFetch(body: unknown, status = 200) {
  const response =
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("getConnectionStatus", () => {
  it("GETs /api/v1/slack/oauth/status with the bearer token", async () => {
    const status = {
      connected: true,
      team_name: "T",
      team_id: "T1",
      bot_user_id: "B1",
      connected_at: "2026-01-01",
    };
    const spy = mockFetch(status);

    const result = await getConnectionStatus("test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/slack/oauth/status");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(status);
  });

  it("throws a plain Error with the backend detail on failure", async () => {
    mockFetch({ detail: "Slack plugin disabled" }, 403);

    const error = await getConnectionStatus("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(Error);
    expect(error).not.toHaveProperty("fieldErrors");
    expect((error as Error).message).toBe(
      "Failed to fetch connection status: Slack plugin disabled",
    );
  });

  it("lets network failures propagate untouched", async () => {
    const boom = new TypeError("Failed to fetch");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(boom);

    await expect(getConnectionStatus("test-token")).rejects.toBe(boom);
  });
});

describe("getAuthorizationUrl", () => {
  it("GETs the authorize endpoint and unwraps the url", async () => {
    const spy = mockFetch({ url: "https://slack.com/install/x" });

    const result = await getAuthorizationUrl("test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/slack/oauth/authorize");
    expect(result).toBe("https://slack.com/install/x");
  });

  it("prefixes failures with the action", async () => {
    mockFetch({ detail: "not configured" }, 400);

    await expect(getAuthorizationUrl("test-token")).rejects.toThrow(
      "Failed to get authorization URL: not configured",
    );
  });
});

describe("disconnectSlack", () => {
  it("DELETEs the disconnect endpoint and resolves", async () => {
    const spy = mockFetch({ ok: true });

    await expect(disconnectSlack("test-token")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/slack/oauth/disconnect");
    expect(request.method).toBe("DELETE");
  });
});

describe("fetchLogs", () => {
  it("GETs /api/v1/slack/logs without query params by default", async () => {
    const logs = { items: [], total: 0, next_cursor: null, has_more: false };
    const spy = mockFetch(logs);

    const result = await fetchLogs("test-token", {});

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/slack/logs");
    expect(url.search).toBe("");
    expect(result).toEqual(logs);
  });

  it("serializes limit, cursor and since_id when given", async () => {
    const spy = mockFetch({ items: [], total: 0, next_cursor: null, has_more: false });

    await fetchLogs("test-token", { limit: 25, cursor: "abc", sinceId: 7 });

    const url = new URL(sentRequest(spy).url);
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("cursor")).toBe("abc");
    expect(url.searchParams.get("since_id")).toBe("7");
  });
});

describe("fetchRagSources", () => {
  it("GETs /api/v1/slack/rag/sources", async () => {
    const spy = mockFetch({ sources: ["Doc A"] });

    const result = await fetchRagSources("test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/slack/rag/sources");
    expect(result).toEqual({ sources: ["Doc A"] });
  });
});
