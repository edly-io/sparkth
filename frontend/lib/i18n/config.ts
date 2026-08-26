export const LOCALE_COOKIE = "NEXT_LOCALE";

// The catalogs bundled with the frontend (messages/<locale>.json); the user-facing
// picker reads the authoritative allowlist from GET /api/v1/languages instead.
export const locales = ["en", "es", "fr"] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

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
