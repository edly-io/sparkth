import { describe, it, expect, vi, beforeEach } from "vitest";

import { buildDailySeries, fetchLoginActivity, summarize } from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "./test-utils";

// authMiddleware reads the stored token; stub it to null so the explicit bearer
// header from the client is what we assert on (mirrors lib/tests/llm.test.ts).
vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchLoginActivity", () => {
  it("GETs /api/v1/analytics/login-activity with days and the bearer token", async () => {
    const points = [{ day: "2026-07-20", login_count: 3 }];
    const spy = mockFetch(points);

    const result = await fetchLoginActivity("test-token", { days: 30 });

    const request = sentRequest(spy);
    const url = new URL(request.url);
    expect(url.pathname).toBe("/api/v1/analytics/login-activity");
    expect(url.searchParams.get("days")).toBe("30");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("defaults to 30 days when none is given", async () => {
    const spy = mockFetch([]);

    await fetchLoginActivity("test-token");

    expect(new URL(sentRequest(spy).url).searchParams.get("days")).toBe("30");
  });

  it("wraps a transport failure as an ApiRequestError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await fetchLoginActivity("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toMatch(/unable to connect/i);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchLoginActivity("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(403);
  });
});

describe("buildDailySeries", () => {
  it("zero-fills a continuous oldest→newest series over the window", () => {
    const now = new Date("2026-07-23T12:00:00Z");
    const points = [
      { day: "2026-07-23", login_count: 5 },
      { day: "2026-07-21", login_count: 2 },
    ];

    const series = buildDailySeries(points, 3, now);

    expect(series).toEqual([
      { label: "2026-07-21", value: 2 },
      { label: "2026-07-22", value: 0 },
      { label: "2026-07-23", value: 5 },
    ]);
  });
});

describe("summarize", () => {
  it("derives total logins and the busiest day from a windowed series", () => {
    const series = [
      { label: "2026-07-21", value: 2 },
      { label: "2026-07-22", value: 0 },
      { label: "2026-07-23", value: 5 },
    ];

    const { total, busiest } = summarize(series);

    expect(total).toBe(7);
    expect(busiest).toEqual({ label: "2026-07-23", value: 5 });
  });

  it("returns zero total and null busiest for an empty series", () => {
    expect(summarize([])).toEqual({ total: 0, busiest: null });
  });
});
