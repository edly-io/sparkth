// Adds this plugin's namespace to the catalog type next-intl checks message keys against.

import type catalog from "@/plugins/compose/src/i18n/en.json";

type Catalog = typeof catalog;

declare module "@/lib/i18n/messages" {
  interface PluginMessages extends Catalog {}
}
