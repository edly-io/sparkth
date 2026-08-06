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

type SidebarPlugin = UserPluginState & { sidebar: NonNullable<UserPluginState["sidebar"]> };

/**
 * Sidebar items for the enabled plugins that have a frontend registration and
 * declared a sidebar entry, sorted by their declared order.
 */
export function sidebarItemsFrom(userPlugins: UserPluginState[]): SidebarItem[] {
  return userPlugins
    .filter(
      (plugin): plugin is SidebarPlugin =>
        plugin.enabled && plugin.has_frontend && plugin.sidebar != null,
    )
    .sort((a, b) => a.sidebar.order - b.sidebar.order)
    .map((plugin) => ({
      name: plugin.plugin_name,
      label: plugin.sidebar.label,
      icon: plugin.sidebar.icon,
      description: plugin.display?.description,
    }));
}
