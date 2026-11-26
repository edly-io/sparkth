import { describe, it, expect, vi, beforeEach } from "vitest";

import { createRole, deleteRole, listGroups, listRoles } from "@/core/permissions/client";

import { mockFetch, sentRequest } from "@/tests/lib/utils";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
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

describe("deleteRole", () => {
  it("DELETEs /api/v1/permissions/roles/{id}", async () => {
    const spy = mockFetch(null, 204);

    await deleteRole("test-token", 5);

    const request = sentRequest(spy);
    expect(request.method).toBe("DELETE");
    expect(new URL(request.url).pathname).toBe("/api/v1/permissions/roles/5");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
  });
});
