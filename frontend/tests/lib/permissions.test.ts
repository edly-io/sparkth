import { describe, it, expect, vi, beforeEach } from "vitest";

import { checkPermission } from "@/lib/permissions";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "./test-utils";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("checkPermission", () => {
  it("GETs /api/v1/permissions/can with the permission + bearer token and returns allowed", async () => {
    const spy = mockFetch({ allowed: true });

    const result = await checkPermission("test-token", "analytics.read");

    const request = sentRequest(spy);
    const url = new URL(request.url);
    expect(url.pathname).toBe("/api/v1/permissions/can");
    expect(url.searchParams.get("permission")).toBe("analytics.read");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toBe(true);
  });

  it("returns false when the backend says not allowed", async () => {
    mockFetch({ allowed: false });

    expect(await checkPermission("test-token", "analytics.read")).toBe(false);
  });

  it("forwards a non-global scope and object id as query params", async () => {
    const spy = mockFetch({ allowed: true });

    await checkPermission("test-token", "analytics.read", { scope: "course", scopeObjectId: "42" });

    const url = new URL(sentRequest(spy).url);
    expect(url.searchParams.get("scope")).toBe("course");
    expect(url.searchParams.get("scope_object_id")).toBe("42");
  });

  it("throws rather than quietly answering false when the response carries no body", async () => {
    mockFetch(null, 204);

    await expect(checkPermission("test-token", "analytics.read")).rejects.toThrow();
  });

  it("wraps a transport failure as an ApiRequestError rather than answering false", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await checkPermission("test-token", "analytics.read").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toMatch(/unable to connect/i);
  });

  it("types the permission argument so an unknown name is a compile error", () => {
    // Guard enforced by `tsc` (not at runtime): the permission argument is a PermissionName
    // union, not a bare string, so a typo — which would otherwise fail closed and silently —
    // won't compile. If the param were loosened back to `string`, this @ts-expect-error would
    // be unused and the typecheck step would fail.
    // @ts-expect-error "analytics.raed" is not a registered PermissionName
    const typo: Parameters<typeof checkPermission>[1] = "analytics.raed";
    expect(typo).toBe("analytics.raed");
  });
});
