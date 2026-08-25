import { getAllPlugins, type PluginDefinition } from "@/lib/plugins";

import { defaultLocale, type Locale } from "./config";

import en from "@/messages/en.json";
import type chatMessages from "@/plugins/chat/messages/en.json";

type CoreMessages = typeof en;
type PluginMessages = typeof chatMessages;

// The full catalog shape next-intl's types are bound to: the core catalog
// plus one namespace per plugin that ships messages. A plugin that adds
// catalogs intersects its `en.json` type into PluginMessages above
// (type-only, so the plugin stays a self-contained runtime unit); the
// step-by-step wiring lives in docs/guides/frontend-plugins.md.
export type Messages = CoreMessages & PluginMessages;

// What the loader actually delivers: plugin namespaces can be absent while
// their chunks load or when one fails. next-intl accepts partial messages
// and reports a missing key at lookup instead of failing the render.
export type LoadedMessages = CoreMessages & Partial<PluginMessages>;

// Dynamic imports so each locale becomes its own chunk and only the active one is fetched.
const catalogs: Record<Locale, () => Promise<{ default: CoreMessages }>> = {
  en: () => import("@/messages/en.json"),
  es: () => import("@/messages/es.json"),
  fr: () => import("@/messages/fr.json"),
};

async function loadPluginMessages(locale: Locale): Promise<Record<string, unknown>[]> {
  return Promise.all(
    getAllPlugins()
      .filter(
        (
          plugin,
        ): plugin is PluginDefinition & {
          loadMessages: NonNullable<PluginDefinition["loadMessages"]>;
        } => plugin.loadMessages !== undefined,
      )
      .map(async (plugin) => {
        try {
          return await plugin.loadMessages(locale);
        } catch (error) {
          console.error(
            `i18n: failed to load the "${locale}" catalog of plugin "${plugin.name}"`,
            error,
          );
          if (locale === defaultLocale) return {};
          try {
            return await plugin.loadMessages(defaultLocale);
          } catch (fallbackError) {
            console.error(
              `i18n: failed to load the "${defaultLocale}" fallback catalog of plugin "${plugin.name}"`,
              fallbackError,
            );
            return {};
          }
        }
      }),
  );
}

// Merges the core catalog with every registered plugin's catalog. A catalog
// that fails to load, core or plugin, falls back to its English counterpart
// (a plugin whose English catalog also fails is skipped), so one broken
// chunk never takes down the others.
export async function loadMessages(locale: Locale): Promise<LoadedMessages> {
  const [core, pluginCatalogs] = await Promise.all([
    catalogs[locale]()
      .then((chunk) => chunk.default)
      .catch((error: unknown) => {
        console.error(
          `i18n: failed to load the "${locale}" core catalog, falling back to English`,
          error,
        );
        return en;
      }),
    loadPluginMessages(locale),
  ]);
  return Object.assign({}, core, ...pluginCatalogs) as LoadedMessages;
}
