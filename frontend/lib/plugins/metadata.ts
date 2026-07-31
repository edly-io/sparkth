/**
 * Helpers over the backend-declared plugin metadata carried on UserPluginState.
 *
 * The backend is the single source of truth for a plugin's display name,
 * description, icon, and sidebar entry; these helpers read that metadata off
 * the API response instead of a frontend-side copy.
 */

import type { UserPluginState } from "./types";

/** A sidebar navigation item derived from a backend-declared sidebar entry. */
export interface SidebarItem {
  name: string;
  label: string;
  icon?: string | null;
  description?: string | null;
}

/** The backend-declared display name, falling back to the plugin name. */
export function displayNameOf(plugin: UserPluginState): string {
  return plugin.display?.display_name ?? plugin.plugin_name;
}

const DEFAULT_SIDEBAR_ORDER = 100;

/**
 * Sidebar items for the enabled plugins that declared a sidebar entry,
 * sorted by their declared order.
 */
export function sidebarItemsFrom(userPlugins: UserPluginState[]): SidebarItem[] {
  return userPlugins
    .filter((plugin) => plugin.enabled && plugin.sidebar)
    .sort(
      (a, b) =>
        (a.sidebar?.order ?? DEFAULT_SIDEBAR_ORDER) - (b.sidebar?.order ?? DEFAULT_SIDEBAR_ORDER),
    )
    .map((plugin) => ({
      name: plugin.plugin_name,
      label: plugin.sidebar!.label,
      icon: plugin.sidebar!.icon,
      description: plugin.display?.description,
    }));
}
