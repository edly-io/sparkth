import type { Locale } from "./config";

import type en from "@/messages/en.json";

export type Messages = typeof en;

// One dynamic import per catalog so the bundler splits each locale into its own
// chunk and only the active one is fetched.
const catalogs: Record<Locale, () => Promise<{ default: Messages }>> = {
  en: () => import("@/messages/en.json"),
  es: () => import("@/messages/es.json"),
  fr: () => import("@/messages/fr.json"),
};

export async function loadMessages(locale: Locale): Promise<Messages> {
  const catalog = await catalogs[locale]();
  return catalog.default;
}
