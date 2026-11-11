import { describe, it, expect, vi, beforeEach } from "vitest";

import { addWhitelistEntry, getWhitelist, removeWhitelistEntry } from "@/core/whitelist/client";

import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("whitelist", () => {
  it("getWhitelist sends the explicit bearer token", async () => {
    const entries = [{ id: 1, value: "a@b.c", entry_type: "email", created_at: "2026-01-01" }];
    const spy = mockFetch(entries);

    const result = await getWhitelist("admin-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/whitelist/");
    expect(request.headers.get("authorization")).toBe("Bearer admin-token");
    expect(result).toEqual(entries);
  });

  it("addWhitelistEntry POSTs the value with the explicit token", async () => {
    const entry = { id: 2, value: "x@y.z", entry_type: "email", created_at: "2026-01-01" };
    const spy = mockFetch(entry, 201);

    const result = await addWhitelistEntry("admin-token", "x@y.z");

    const request = sentRequest(spy);
    expect(request.method).toBe("POST");
    await expect(request.clone().json()).resolves.toEqual({ value: "x@y.z" });
    expect(request.headers.get("authorization")).toBe("Bearer admin-token");
    expect(result).toEqual(entry);
  });

  it("removeWhitelistEntry DELETEs the entry by id and resolves on 204", async () => {
    const spy = mockFetch(null, 204);

    await expect(removeWhitelistEntry("admin-token", 3)).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(request.method).toBe("DELETE");
    expect(new URL(request.url).pathname).toBe("/api/v1/whitelist/3");
  });
});
