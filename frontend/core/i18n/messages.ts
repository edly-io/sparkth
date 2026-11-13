import { getAllPlugins } from "@/core/plugins/registry";
import type { PluginDefinition } from "@/core/plugins/types";
import { defaultLocale, type Locale } from "@/lib/i18n/config";
import type { CoreMessages, LoadedMessages } from "@/lib/i18n/messages";

import en from "@/core/i18n/catalogs/en";

// Dynamic imports so each locale becomes its own chunk and only the active one is fetched.
const catalogs: Record<Locale, () => Promise<{ default: CoreMessages }>> = {
  en: () => import("@/core/i18n/catalogs/en"),
  es: () => import("@/core/i18n/catalogs/es"),
  fr: () => import("@/core/i18n/catalogs/fr"),
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

/**
 * Merges the core catalog with every registered plugin's catalog. A catalog that fails to load,
 * core or plugin, falls back to its English counterpart (a plugin whose English catalog also
 * fails is skipped), so one broken chunk never takes down the others.
 */
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
