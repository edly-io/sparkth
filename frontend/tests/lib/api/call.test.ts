import { describe, it, expect } from "vitest";

import { ApiRequestError, call } from "@/lib/api";

// `call` is the shared unwrap-and-normalise wrapper every lib/* client builds on, so its
// error contract is pinned here rather than re-tested per client.
describe("call", () => {
  it("unwraps the data of a successful request", async () => {
    const result = await call<{ ok: boolean }>(async () => ({ data: { ok: true } }));

    expect(result).toEqual({ ok: true });
  });

  it("rethrows an ApiRequestError untouched", async () => {
    const original = new ApiRequestError({ message: "nope", fieldErrors: {} }, 403);

    const error = await call(() => Promise.reject(original)).catch((e: unknown) => e);

    expect(error).toBe(original);
  });

  it("wraps a transport failure as an ApiRequestError", async () => {
    const error = await call(() => Promise.reject(new TypeError("network down"))).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("Unable to connect to server: network down");
  });

  it("preserves an AbortError so callers can tell cancellation from failure", async () => {
    const aborted = new DOMException("aborted", "AbortError");

    const error = await call(() => Promise.reject(aborted)).catch((e: unknown) => e);

    expect(error).toBe(aborted);
  });
});
