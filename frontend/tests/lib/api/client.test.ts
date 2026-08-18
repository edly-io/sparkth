import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { api } from "@/lib/api/client";
import { LOCALE_COOKIE } from "@/lib/i18n/config";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn(),
}));

import { getStoredToken } from "@/lib/auth-tokens";

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(getStoredToken).mockReturnValue(null);
    document.cookie = `${LOCALE_COOKIE}=; path=/; max-age=0`;
  });

  it("injects the bearer token from storage when present", async () => {
    vi.mocked(getStoredToken).mockReturnValue("stored-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await api.GET("/api/v1/user/me");

    const request = fetchSpy.mock.calls[0][0] as Request;
    expect(new URL(request.url).pathname).toBe("/api/v1/user/me");
    expect(request.headers.get("authorization")).toBe("Bearer stored-token");
  });

  it("lets an explicit Authorization header win over the stored token", async () => {
    vi.mocked(getStoredToken).mockReturnValue("stored-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await api.GET("/api/v1/user/me", {
      headers: { Authorization: "Bearer explicit-token" },
    });

    const request = fetchSpy.mock.calls[0][0] as Request;
    expect(request.headers.get("authorization")).toBe("Bearer explicit-token");
  });

  it("sends no authorization header when storage is empty", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await api.GET("/api/v1/user/me");

    const request = fetchSpy.mock.calls[0][0] as Request;
    expect(request.headers.get("authorization")).toBeNull();
  });

  it("sends Accept-Language from the locale cookie", async () => {
    document.cookie = `${LOCALE_COOKIE}=es`;
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await api.GET("/api/v1/user/me");

    const request = fetchSpy.mock.calls[0][0] as Request;
    expect(request.headers.get("accept-language")).toBe("es");
  });

  it("sends the default locale when no locale cookie is set", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));

    await api.GET("/api/v1/user/me");

    const request = fetchSpy.mock.calls[0][0] as Request;
    expect(request.headers.get("accept-language")).toBe("en");
  });

  it("throws ApiRequestError carrying status and detail on non-ok responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }),
    );

    const error = await api.GET("/api/v1/user/me").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(401);
    expect((error as ApiRequestError).message).toBe("Not authenticated");
  });

  it("forwards structured detail (code, data) for callers that branch on it", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "email_not_verified", email: "u@example.com" } }),
        { status: 403 },
      ),
    );

    const error = await api.GET("/api/v1/user/me").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(403);
    expect((error as ApiRequestError).code).toBe("email_not_verified");
    expect((error as ApiRequestError).data).toEqual({
      code: "email_not_verified",
      email: "u@example.com",
    });
  });

  it("throws a generic ApiRequestError when the error body is not json", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("boom", { status: 502 }));

    const error = await api.GET("/api/v1/user/me").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(502);
  });

  it("returns parsed data on success", async () => {
    const user = { id: "1", username: "h" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), { status: 200 }),
    );

    const { data } = await api.GET("/api/v1/user/me");

    expect(data).toEqual(user);
  });
});
