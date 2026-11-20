import { describe, it, expect, vi, beforeEach } from "vitest";

import { checkPermission, checkPermissions } from "@/core/permissions/client";
import { ApiRequestError } from "@/lib/api";

import { mockFetch, sentRequest } from "@/tests/lib/utils";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("checkPermission", () => {
  it("POSTs the permission to /api/v1/permissions/can with the bearer token and returns allowed", async () => {
    const spy = mockFetch({ allowed: true });

    const result = await checkPermission("test-token", "analytics.read", { scope: "global" });

    const request = sentRequest(spy);
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/can");
    expect(await request.json()).toEqual({ permission: "analytics.read", scope: "global" });
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toBe(true);
  });

  it("returns false when the backend says not allowed", async () => {
    mockFetch({ allowed: false });

    expect(await checkPermission("test-token", "analytics.read", { scope: "global" })).toBe(false);
  });

  it("sends a non-global scope and object id in the body", async () => {
    const spy = mockFetch({ allowed: true });

    await checkPermission("test-token", "analytics.read", { scope: "course", scopeObjectId: "42" });

    expect(await sentRequest(spy).json()).toEqual({
      permission: "analytics.read",
      scope: "course",
      scope_object_id: "42",
    });
  });

  it("throws rather than quietly answering false when the response carries no body", async () => {
    mockFetch(null, 204);

    await expect(
      checkPermission("test-token", "analytics.read", { scope: "global" }),
    ).rejects.toThrow();
  });

  it("wraps a transport failure as an ApiRequestError rather than answering false", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await checkPermission("test-token", "analytics.read", { scope: "global" }).catch(
      (e: unknown) => e,
    );

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

describe("checkPermissions", () => {
  it("POSTs every check to /api/v1/permissions/can/batch and returns the answers in order", async () => {
    const spy = mockFetch([
      { permission: "analytics.read", scope: "global", scope_object_id: null, allowed: true },
      { permission: "group.read", scope: "group", scope_object_id: "7", allowed: false },
    ]);

    const result = await checkPermissions("test-token", [
      { permission: "analytics.read", scope: "global" },
      { permission: "group.read", scope: "group", scopeObjectId: "7" },
    ]);

    const request = sentRequest(spy);
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/can/batch");
    expect(await request.json()).toEqual([
      { permission: "analytics.read", scope: "global" },
      { permission: "group.read", scope: "group", scope_object_id: "7" },
    ]);
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual([true, false]);
  });

  it("wraps a transport failure as an ApiRequestError rather than answering false", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await checkPermissions("test-token", [
      { permission: "analytics.read", scope: "global" },
    ]).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
  });
});
