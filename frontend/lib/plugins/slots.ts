/**
 * The slot through which a plugin with a page tells core it exists.
 *
 * A plugin sets its `PluginDefinition` under its name, the name its backend plugin declares. Core
 * registers every definition in the slot, so it serves the plugin's page and loads its message
 * catalogs without knowing about any plugin itself.
 */

import type { PluginDefinition } from "@/core/plugins/types";

/** Each plugin's definition, set by the plugin under its name. */
export const PLUGINS: Map<string, PluginDefinition> = new Map();
