import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError, getCurrentUser } from "./api";

describe("getCurrentUser", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/v1/user/me with the bearer token and returns the user", async () => {
    const user = { id: "1", username: "h", email: "h@example.com" };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(user), { status: 200 }));

    const result = await getCurrentUser("test-token");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/user/me",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
          Accept: "application/json",
        }),
      }),
    );
    expect(result).toEqual(user);
  });

  it("throws ApiRequestError carrying the status on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }),
    );

    const error = await getCurrentUser("expired-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(401);
  });
});
