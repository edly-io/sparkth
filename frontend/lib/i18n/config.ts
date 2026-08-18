// Locale selection for the static-UI translation layer. Production is a static
// export served by FastAPI, so there is no server to negotiate the locale: it is
// resolved client-side from a cookie, and the same cookie value is echoed to the
// backend as Accept-Language so both sides always agree.

export const LOCALE_COOKIE = "NEXT_LOCALE";

// The locales a message catalog ships for (messages/<locale>.json). The user-facing
// picker reads the authoritative allowlist from GET /api/v1/languages; this list
// only names the catalogs bundled with the frontend.
export const locales = ["en", "es", "fr"] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

// Reads the locale cookie, falling back to the default locale when the cookie is
// absent, holds an unsupported tag, or there is no document (build-time prerender).
export function readLocaleCookie(): Locale {
  if (typeof document === "undefined") return defaultLocale;
  const entry = document.cookie.split("; ").find((c) => c.startsWith(`${LOCALE_COOKIE}=`));
  const value = entry?.slice(LOCALE_COOKIE.length + 1);
  if (value !== undefined && isLocale(value)) return value;
  return defaultLocale;
}

export function setLocaleCookie(locale: Locale): void {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
}
