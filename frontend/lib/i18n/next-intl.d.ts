// Type augmentation wiring next-intl to our catalogs: message keys passed to
// useTranslations/t() are checked against the English catalog at compile time,
// and locale parameters are narrowed to the supported tags.

import type en from "@/messages/en.json";

import type { Locale } from "./config";

declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof en;
  }
}
