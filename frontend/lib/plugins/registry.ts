import { PluginDefinition } from './types';

const pluginRegistry = new Map<string, PluginDefinition>();

export function registerPlugin(plugin: PluginDefinition) {
  pluginRegistry.set(plugin.name, plugin);
}

export function getPlugin(name: string): PluginDefinition | undefined {
  return pluginRegistry.get(name);
}

export function getAllPlugins(): PluginDefinition[] {
  return Array.from(pluginRegistry.values());
}

export function getPluginsByNames(names: string[]): PluginDefinition[] {
  return names
    .map(name => pluginRegistry.get(name))
    .filter((plugin): plugin is PluginDefinition => plugin !== undefined);
}

export type { PluginDefinition };
