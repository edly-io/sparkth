import { vi } from "vitest";

// Shared helpers for the lib/* client tests, which all exercise the openapi-fetch
// client by spying on globalThis.fetch.

// Stubs globalThis.fetch with a single resolved Response and returns the spy.
// A 204 yields an empty body; everything else serializes `body` as JSON.
export function mockFetch(body: unknown, status = 200) {
  const response =
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

// Returns the Request the client passed to fetch on its first call.
export function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}
