/**
 * Helpers over the plugin state the backend declares on PluginState.
 *
 * The backend is the single source of truth for a plugin's display name,
 * description, icon, and sidebar entry, and for the two switches that decide
 * whether it is usable: the user's own and the system-wide one. These helpers
 * read all of it off the API response instead of a frontend-side copy.
 */

import type { PluginState } from "./types";

/** Whether the plugin is usable: on for the user and on system-wide. */
export function isPluginUsable(plugin: PluginState): boolean {
  return plugin.enabled && plugin.system_enabled;
}

/** The backend-declared display name, falling back to the plugin name. */
export function displayNameOf(plugin: PluginState): string {
  return plugin.display?.display_name ?? plugin.plugin_name;
}
