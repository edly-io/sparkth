import { describe, it, expect, vi, beforeEach } from "vitest";

import { fetchLoginActivity } from "@/lib/analytics";

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
});
