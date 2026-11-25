import { describe, it, expect, vi, beforeEach } from "vitest";

import { checkPermissions, createRole, listGroups, listRoles } from "@/core/permissions/client";
import { ApiRequestError } from "@/lib/api";

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

describe("listRoles", () => {
  it("GETs /api/v1/permissions/roles and returns the roles", async () => {
    const roles = [
      { id: 1, name: "admin", description: "Everything", permissions: [], is_builtin: true },
    ];
    const spy = mockFetch(roles);

    const result = await listRoles("test-token");

    const request = sentRequest(spy);
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/roles");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(roles);
  });
});

describe("listGroups", () => {
  it("GETs /api/v1/permissions/groups and returns the groups", async () => {
    const groups = [{ id: 3, name: "Editors", description: null }];
    const spy = mockFetch(groups);

    const result = await listGroups("test-token");

    const request = sentRequest(spy);
    expect(request.method).toBe("GET");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/groups");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(groups);
  });
});

describe("createRole", () => {
  it("POSTs the name and description to /api/v1/permissions/roles and returns the new role", async () => {
    const created = { id: 9, name: "Grader", description: "Marks work." };
    const spy = mockFetch(created, 201);

    const result = await createRole("test-token", { name: "Grader", description: "Marks work." });

    const request = sentRequest(spy);
    expect(request.method).toBe("POST");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/roles");
    expect(await request.json()).toEqual({ name: "Grader", description: "Marks work." });
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(created);
  });
});
