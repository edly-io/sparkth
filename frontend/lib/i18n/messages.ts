import type en from "@/core/i18n/catalogs/en";

/** The core catalog's shape: every core namespace, without any plugin's. */
export type CoreMessages = typeof en;

/**
 * One namespace per plugin that ships messages. Empty here: each such plugin
 * adds its English catalog's type from its own `i18n/messages.d.ts`.
 */
export interface PluginMessages {}

/**
 * The full catalog shape next-intl's types are bound to: the core catalog plus every plugin's
 * namespace.
 */
export type Messages = CoreMessages & PluginMessages;

/**
 * What the loader actually delivers: plugin namespaces can be absent while their chunks load or
 * when one fails. next-intl accepts partial messages and reports a missing key at lookup instead
 * of failing the render.
 */
export type LoadedMessages = CoreMessages & Partial<PluginMessages>;
