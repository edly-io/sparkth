// Adds this plugin's namespace to the catalog type next-intl checks message keys against.

import type catalog from "@/plugins/compose/messages/en.json";

type Catalog = typeof catalog;

declare module "@/lib/i18n/messages" {
  interface PluginMessages extends Catalog {}
}
