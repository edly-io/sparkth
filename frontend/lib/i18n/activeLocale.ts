import en from "@/messages/en.json";

import { defaultLocale, type Locale } from "./config";
import type { LoadedMessages } from "./messages";

// The locale the UI is rendering right now, maintained by LocaleProvider. The
// NEXT_LOCALE cookie stores the *preference*; this tracks what is on screen, and the
// two diverge when the catalog load fails outright and the UI stays on the default
// locale (a single failed chunk instead falls back to its English counterpart). API calls read this value so Accept-Language always matches what the user
// sees rather than what the cookie asks for. Code outside React translates with the
// catalog recorded alongside it.
let activeLocale: Locale = defaultLocale;
let activeMessages: LoadedMessages = en;

export function getActiveLocale(): Locale {
  return activeLocale;
}

export function setActiveLocale(locale: Locale): void {
  activeLocale = locale;
}

export function getActiveMessages(): LoadedMessages {
  return activeMessages;
}

export function setActiveMessages(messages: LoadedMessages): void {
  activeMessages = messages;
}
