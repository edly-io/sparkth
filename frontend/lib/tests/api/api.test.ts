import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  ApiRequestError,
  addWhitelistEntry,
  getCurrentUser,
  getGoogleLoginUrl,
  getWhitelist,
  login,
  register,
  removeWhitelistEntry,
  resendVerificationEmail,
  verifyEmail,
} from "@/lib/api";

import { mockFetch, sentRequest } from "../test-utils";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("login", () => {
  it("POSTs credentials to /api/v1/auth/login and returns the token payload", async () => {
    const token = { access_token: "t", token_type: "bearer", expires_at: "2026-01-01T00:00:00Z" };
    const spy = mockFetch(token);

    const result = await login({ username: "h", password: "pw" });

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/auth/login");
    expect(request.method).toBe("POST");
    await expect(request.clone().json()).resolves.toEqual({ username: "h", password: "pw" });
    expect(result).toEqual(token);
  });

  it("maps validation envelopes to fieldErrors", async () => {
    mockFetch(
      { detail: [{ loc: ["body", "username"], msg: "Field required", type: "missing" }] },
      422,
    );

    const error = await login({ username: "", password: "" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).fieldErrors).toEqual({ username: "Field required" });
    expect((error as ApiRequestError).status).toBe(422);
  });

  it("surfaces structured detail for unverified-email branching", async () => {
    mockFetch({ detail: { code: "email_not_verified", email: "u@example.com" } }, 403);

    const error = await login({ username: "h", password: "pw" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).code).toBe("email_not_verified");
    expect((error as ApiRequestError).data?.email).toBe("u@example.com");
  });

  it("wraps network failures as connection errors", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await login({ username: "h", password: "pw" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("Unable to connect to server: Failed to fetch");
  });

  it("propagates an aborted request instead of wrapping it as a connection error", async () => {
    const abort = new DOMException("The operation was aborted.", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abort);

    const error = await login({ username: "h", password: "pw" }).catch((e: unknown) => e);

    expect(error).toBe(abort);
    expect(error).not.toBeInstanceOf(ApiRequestError);
  });
});

describe("register", () => {
  it("POSTs the registration payload and returns the created user", async () => {
    const user = {
      id: 1,
      name: "H",
      username: "h",
      email: "h@example.com",
      is_superuser: false,
      email_verified: false,
    };
    const spy = mockFetch(user);

    const result = await register({
      name: "H",
      username: "h",
      email: "h@example.com",
      password: "pw",
    });

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/auth/register");
    expect(request.method).toBe("POST");
    expect(result).toEqual(user);
  });
});

describe("getGoogleLoginUrl", () => {
  it("GETs the authorize endpoint and returns the url payload", async () => {
    const spy = mockFetch({ url: "https://accounts.google.com/x" });

    const result = await getGoogleLoginUrl();

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/auth/google/authorize");
    expect(result).toEqual({ url: "https://accounts.google.com/x" });
  });
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

describe("verifyEmail", () => {
  it("POSTs the token and resolves on 204", async () => {
    const spy = mockFetch(null, 204);

    await expect(verifyEmail("verification-token")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/auth/verify-email");
    await expect(request.clone().json()).resolves.toEqual({ token: "verification-token" });
  });

  it("keeps the response status on failure", async () => {
    mockFetch({ detail: "Token expired" }, 400);

    const error = await verifyEmail("stale").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(400);
    expect((error as ApiRequestError).message).toBe("Token expired");
  });
});

describe("resendVerificationEmail", () => {
  it("resolves on 202", async () => {
    const spy = mockFetch({ message: "sent" }, 202);

    await expect(resendVerificationEmail("u@example.com")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/auth/verify-email/resend");
    await expect(request.clone().json()).resolves.toEqual({ email: "u@example.com" });
  });

  it("throws the rate_limited sentinel on 429", async () => {
    mockFetch({ detail: "Too many requests" }, 429);

    const error = await resendVerificationEmail("u@example.com").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("rate_limited");
    expect((error as ApiRequestError).status).toBe(429);
  });

  it("throws the fixed resend message on other failures", async () => {
    mockFetch({ detail: "boom" }, 500);

    const error = await resendVerificationEmail("u@example.com").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe(
      "Could not resend confirmation email. Please try again.",
    );
    expect((error as ApiRequestError).status).toBe(500);
  });
});

describe("getCurrentUser", () => {
  it("GETs /api/v1/user/me with the explicit bearer token and returns the user", async () => {
    const user = {
      id: 1,
      name: "H",
      username: "h",
      email: "h@example.com",
      is_superuser: false,
      email_verified: true,
    };
    const spy = mockFetch(user);

    const result = await getCurrentUser("test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/user/me");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(user);
  });

  it("throws ApiRequestError carrying the status on non-ok response", async () => {
    mockFetch({ detail: "Not authenticated" }, 401);

    const error = await getCurrentUser("expired-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(401);
  });

  it("wraps network failures as connection errors", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await getCurrentUser("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("Unable to connect to server: Failed to fetch");
  });

  it("re-throws AbortError unwrapped so callers can ignore aborted requests", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abortError);

    await expect(getCurrentUser("test-token")).rejects.toBe(abortError);
  });
});
