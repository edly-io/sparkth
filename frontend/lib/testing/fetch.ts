import { vi } from "vitest";

/**
 * Stubs `globalThis.fetch` with a single resolved Response and returns the spy, for testing a
 * client built on the API client. A 204 yields an empty body; anything else serializes `body`.
 */
export function mockFetch(body: unknown, status = 200) {
  const response =
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

/** The Request the client passed to `fetch` on its first call. */
export function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}
