import { describe, it, expect, vi, beforeEach } from "vitest";

import { fetchLogins } from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "../test-utils";

// authMiddleware reads the stored token; stub it to null so the explicit bearer
// header from the client is what we assert on (mirrors lib/tests/llm.test.ts).
vi.mock("@/lib/auth-tokens", () => ({
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
