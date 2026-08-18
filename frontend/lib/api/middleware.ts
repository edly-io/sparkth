import type { Middleware } from "openapi-fetch";
import { getStoredToken } from "@/lib/auth-tokens";
import { readLocaleCookie } from "@/lib/i18n/config";
import {
  ApiRequestError,
  formatApiError,
  isStructuredDetail,
  type ApiError,
  type StructuredErrorDetail,
} from "./errors";

export const authMiddleware: Middleware = {
  async onRequest({ request }) {
    // A caller-supplied Authorization header (explicit token param) wins.
    if (request.headers.has("Authorization")) return request;
    const token = getStoredToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

// Echoes the UI locale so backend responses arrive in the language the UI renders.
export const localeMiddleware: Middleware = {
  async onRequest({ request }) {
    request.headers.set("Accept-Language", readLocaleCookie());
    return request;
  },
};

export const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (response.ok) return response;
    let formatted = {
      message: `Request failed (HTTP ${response.status}). Please try again.`,
      fieldErrors: {} as Record<string, string>,
    };
    let detail: StructuredErrorDetail | undefined;
    try {
      const envelope: ApiError = await response.clone().json();
      formatted = formatApiError(envelope);
      if (isStructuredDetail(envelope.detail)) detail = envelope.detail;
    } catch {
      // Non-JSON error body: keep the generic message.
    }
    throw new ApiRequestError(formatted, response.status, detail);
  },
};
