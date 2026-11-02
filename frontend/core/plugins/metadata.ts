/**
 * Helpers over the backend-declared plugin metadata carried on UserPluginState.
 *
 * The backend is the single source of truth for a plugin's display name,
 * description, icon, and sidebar entry; these helpers read that metadata off
 * the API response instead of a frontend-side copy.
 */

import type { UserPluginState } from "./types";

/** The backend-declared display name, falling back to the plugin name. */
export function displayNameOf(plugin: UserPluginState): string {
  return plugin.display?.display_name ?? plugin.plugin_name;
}
