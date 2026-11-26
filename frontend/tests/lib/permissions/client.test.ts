import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { checkPermissions } from "@/lib/permissions/client";

import { mockFetch, sentRequest } from "@/tests/lib/utils";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
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

  it("throws rather than quietly answering false when the response carries no body", async () => {
    mockFetch(null, 204);

    await expect(
      checkPermissions("test-token", [{ permission: "analytics.read", scope: "global" }]),
    ).rejects.toThrow();
  });

  it("wraps a transport failure as an ApiRequestError rather than answering false", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network down"));

    const error = await checkPermissions("test-token", [
      { permission: "analytics.read", scope: "global" },
    ]).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
  });
});
