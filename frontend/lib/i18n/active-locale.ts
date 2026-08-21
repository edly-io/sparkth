import { defaultLocale, type Locale } from "./config";

// The locale the UI is rendering right now, maintained by LocaleProvider. The
// NEXT_LOCALE cookie stores the *preference*; this tracks what is on screen, and the
// two diverge when a catalog chunk fails to load and the UI stays on the default
// locale. API calls read this value so Accept-Language always matches what the user
// sees rather than what the cookie asks for.
let activeLocale: Locale = defaultLocale;

export function getActiveLocale(): Locale {
  return activeLocale;
}

export function setActiveLocale(locale: Locale): void {
  activeLocale = locale;
}
