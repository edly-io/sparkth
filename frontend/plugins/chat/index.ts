import { PluginDefinition } from "@/lib/plugins";
import type { Locale } from "@/lib/i18n/config";

// Dynamic imports so each locale becomes its own chunk, mirroring the core
// catalog loader in lib/i18n/messages.ts.
const messageCatalogs: Record<Locale, () => Promise<{ default: Record<string, unknown> }>> = {
  en: () => import("./messages/en.json"),
  es: () => import("./messages/es.json"),
  fr: () => import("./messages/fr.json"),
};

// Display name, description, icon, and sidebar entry are declared by the
// backend ChatPlugin and arrive via the user-plugins API.
export const chatPlugin: PluginDefinition = {
  name: "chat",
  loadComponent: () => import("./ChatInterface"),
  loadSettingsComponent: () => import("./components/ChatConfigModal"),
  loadMessages: (locale) => messageCatalogs[locale]().then((catalog) => catalog.default),
};
