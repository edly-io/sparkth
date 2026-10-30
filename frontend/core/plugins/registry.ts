import type { PluginDefinition } from "./types";

// The registered plugin definitions, by plugin name.
const plugins = new Map<string, PluginDefinition>();

/**
 * Register a plugin definition.
 *
 * A second registration under a taken name is skipped with a warning, so a plugin module
 * that runs again on hot reload changes nothing.
 * @throws Error when the definition lacks a name or `loadComponent`, or its name is not kebab-case
 */
export function registerPlugin(plugin: PluginDefinition): void {
  if (plugins.has(plugin.name)) {
    console.warn(`Plugin "${plugin.name}" is already registered. Skipping duplicate registration.`);
    return;
  }

  if (!plugin.name || !plugin.loadComponent) {
    throw new Error(`Invalid plugin definition: name and loadComponent are required`);
  }

  if (!/^[a-z][a-z0-9-]*$/.test(plugin.name)) {
    throw new Error(`Invalid plugin name "${plugin.name}". Must be kebab-case (e.g., "my-plugin")`);
  }

  plugins.set(plugin.name, plugin);
  console.debug(`Plugin "${plugin.name}" registered successfully`);
}

/** Unregister the plugin named `name`, running its `onDestroy`. Returns whether it was registered. */
export function unregisterPlugin(name: string): boolean {
  const plugin = plugins.get(name);
  if (!plugin) return false;

  try {
    plugin.onDestroy?.();
  } catch (error) {
    console.error(`Error during plugin "${name}" cleanup:`, error);
  }
  plugins.delete(name);
  return true;
}

/** The plugin registered under `name`, if any. */
export function getPlugin(name: string): PluginDefinition | undefined {
  return plugins.get(name);
}

/** Every registered plugin, in registration order. */
export function getAllPlugins(): PluginDefinition[] {
  return [...plugins.values()];
}
