// Binds next-intl's types to our catalogs, so unknown message keys fail typecheck.

import type en from "@/messages/en.json";

import type { Locale } from "./config";

declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof en;
  }
}
