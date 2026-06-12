import createClient from "openapi-fetch";
import type { components, paths } from "./generated";
import { authMiddleware, errorMiddleware } from "./middleware";

// Use the current origin in browsers (same-origin); fall back to localhost for
// SSR and test environments where relative URLs are not resolvable. See #403.
const baseUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost";

// Pass a fetch wrapper that reads globalThis.fetch at call time so that
// vi.spyOn(globalThis, "fetch") in tests can intercept requests correctly.
const fetchDelegate: typeof fetch = (...args) => globalThis.fetch(...args);

export const api = createClient<paths>({ baseUrl, fetch: fetchDelegate });
api.use(authMiddleware, errorMiddleware);

export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
