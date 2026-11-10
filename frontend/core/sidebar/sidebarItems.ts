import type { UserPluginState } from "@/core/plugins/types";

/** A sidebar navigation item derived from a backend-declared sidebar entry. */
export interface SidebarItem {
  name: string;
  label: string;
  icon?: string | null;
  description?: string | null;
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
