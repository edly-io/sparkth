import { getPlugin } from "@/core/plugins/registry";

/**
 * Whether the plugin is installed: its frontend registered with core. Analytics follow this, not
 * the viewer's or the platform's plugin switches.
 */
export function isInstalled(plugin: string): boolean {
  // ponytail: only a plugin with a page registers; read a backend-reported list if an analytics
  // plugin ever ships without one.
  return getPlugin(plugin) !== undefined;
}
