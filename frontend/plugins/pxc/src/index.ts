import { PluginDefinition } from "@/lib/plugins/types";
import type { Locale } from "@/lib/i18n/config";
// This plugin's contributions to core's slots.
import "@/plugins/pxc/src/slots/icons";
import "@/plugins/pxc/src/slots/settings";

// Dynamic imports so each locale becomes its own chunk and only the active one is fetched.
const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("@/plugins/pxc/src/i18n/en.json"),
  es: () => import("@/plugins/pxc/src/i18n/es.json"),
  fr: () => import("@/plugins/pxc/src/i18n/fr.json"),
};

// Display name, description, icon, and sidebar entry are declared by the
// backend PxcPlugin and arrive via the user-plugins API.
export const pxc: PluginDefinition = {
  name: "pxc",
  loadComponent: () => import("@/plugins/pxc/src/pages/PxcActivities"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};
