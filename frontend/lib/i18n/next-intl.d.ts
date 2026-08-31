// Binds next-intl's types to our catalogs, so unknown message keys fail typecheck.

import type { Locale } from "./config";
import type { Messages } from "./messages";

declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: Messages;
  }
}
