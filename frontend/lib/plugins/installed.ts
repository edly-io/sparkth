import { FRONTEND_PLUGIN_NAMES } from "./generated";

/**
 * Whether the plugin is installed in the backend build. Analytics follow this, not the viewer's
 * or the platform's plugin switches.
 */
export function isInstalled(plugin: string): boolean {
  // ponytail: lists only plugins that declare a frontend page (FRONTEND_APPS); read a
  // backend-reported list if an analytics plugin ever ships without one.
  return (FRONTEND_PLUGIN_NAMES as readonly string[]).includes(plugin);
}
