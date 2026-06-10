import createClient, { type Middleware } from "openapi-fetch";
import { getStoredToken } from "@/lib/auth-tokens";
import { ApiRequestError, formatApiError, type ApiError } from "@/lib/api";
import type { components, paths } from "./generated";

const middleware: Middleware = {
  async onRequest({ request }) {
    const token = getStoredToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  async onResponse({ response }) {
    if (response.ok) return response;
    let formatted = {
      message: `Request failed (HTTP ${response.status}). Please try again.`,
      fieldErrors: {} as Record<string, string>,
    };
    try {
      const envelope: ApiError = await response.clone().json();
      formatted = formatApiError(envelope);
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiRequestError(formatted, response.status);
  },
};

// Use the current origin in browsers (same-origin); fall back to localhost for
// SSR and test environments where relative URLs are not resolvable. See #403.
const baseUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost";

// Pass a fetch wrapper that reads globalThis.fetch at call time so that
// vi.spyOn(globalThis, "fetch") in tests can intercept requests correctly.
const fetchDelegate: typeof fetch = (...args) => globalThis.fetch(...args);

export const api = createClient<paths>({ baseUrl, fetch: fetchDelegate });
api.use(middleware);

export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
