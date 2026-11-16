import { PluginDefinition } from "@/lib/plugins/types";
import { PLUGINS } from "@/lib/plugins/slots";
import type { Locale } from "@/lib/i18n/config";
import { COMPOSE_PLUGIN_NAME } from "@/plugins/compose/src/constants";
// This plugin's contributions to core's slots.
import "@/plugins/compose/src/slots/icons";
import "@/plugins/compose/src/slots/settings";

// Dynamic imports so each locale becomes its own chunk and only the active one is fetched.
const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("@/plugins/compose/src/i18n/en.json"),
  es: () => import("@/plugins/compose/src/i18n/es.json"),
  fr: () => import("@/plugins/compose/src/i18n/fr.json"),
};

// Display name, description, icon, and sidebar entry are declared by the
// backend ComposePlugin and arrive via the user-plugins API.
export const compose: PluginDefinition = {
  name: COMPOSE_PLUGIN_NAME,
  loadComponent: () => import("@/plugins/compose/src/pages/Compose"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};

PLUGINS.set(compose.name, compose);
