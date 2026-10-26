import { describe, it, expect, vi, beforeEach } from "vitest";

import { fetchChatActivity, fetchLogins, fetchSummary } from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

// authMiddleware reads the stored token; stub it to null so the explicit bearer
// header from the client is what we assert on (mirrors lib/tests/llm.test.ts).
vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchLogins", () => {
  it("GETs /api/v1/analytics/logins for a day range with the bearer token", async () => {
    const points = [{ bucket: "2026-07-20", method: "google", login_count: 3 }];
    const spy = mockFetch(points);

    const result = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/analytics/logins");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.get("bucket")).toBe("day");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("wraps a transport failure as an ApiRequestError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toMatch(/unable to connect/i);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchLogins("test-token", { from: "2026-07-01", to: "2026-07-20" }).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("fetchChatActivity", () => {
  it("GETs /api/v1/chat/analytics/activity for a day range with the bearer token", async () => {
    const points = [
      {
        bucket: "2026-07-20",
        event_type: "chat.tool_invoked",
        dimension: "search",
        outcome: null,
        event_count: 2,
      },
    ];
    const spy = mockFetch(points);

    const result = await fetchChatActivity("test-token", { from: "2026-07-01", to: "2026-07-20" });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/chat/analytics/activity");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.get("bucket")).toBe("day");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchChatActivity("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    }).catch((e: unknown) => e);

    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("fetchSummary", () => {
  it("GETs /api/v1/analytics/summary for a range, with no bucket, and the bearer token", async () => {
    const counts = [
      {
        key: "logins",
        label: "Logins",
        view: "logins",
        plugin: null,
        current: 3,
        previous: 1,
      },
    ];
    const spy = mockFetch(counts);

    const result = await fetchSummary("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/analytics/summary");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.has("bucket")).toBe(false);
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(counts);
  });
});
