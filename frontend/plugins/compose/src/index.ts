import { PluginDefinition } from "@/lib/plugins/types";
import type { Locale } from "@/lib/i18n/config";
// This plugin's contributions to core's slots.
import "@/plugins/compose/src/slots/icons";
import "@/plugins/compose/src/slots/settings";

// Dynamic imports so each locale becomes its own chunk and only the active one is fetched.
const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("@/plugins/compose/messages/en.json"),
  es: () => import("@/plugins/compose/messages/es.json"),
  fr: () => import("@/plugins/compose/messages/fr.json"),
};

// Display name, description, icon, and sidebar entry are declared by the
// backend ComposePlugin and arrive via the user-plugins API.
export const compose: PluginDefinition = {
  name: "compose",
  loadComponent: () => import("@/plugins/compose/src/routes/Compose"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};
