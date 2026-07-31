/**
 * Plugin icon resolution.
 *
 * The backend declares icons as lucide icon names (strings); the frontend
 * resolves names to components here. Lucide icons used by backend
 * declarations are mapped explicitly (keeping the bundle tree-shakeable), and
 * plugins can register custom (non-lucide) icon components under a name.
 */

import type { ComponentType } from "react";
import { Plus } from "lucide-react";

export type PluginIcon = ComponentType<{ className?: string }>;

const icons = new Map<string, PluginIcon>([["plus", Plus]]);

/**
 * Register a custom icon component under an icon name (e.g. a brand icon a
 * plugin ships itself). Overrides any built-in mapping for that name.
 */
export function registerPluginIcon(name: string, component: PluginIcon): void {
  icons.set(name, component);
}

/** Resolve an icon name from the API to a component, if one is known. */
export function resolvePluginIcon(name?: string | null): PluginIcon | undefined {
  return name ? icons.get(name) : undefined;
}
