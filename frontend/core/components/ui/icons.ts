/**
 * Plugin icon resolution.
 *
 * The backend declares icons as names; each plugin sets the component for its names in the
 * `PLUGIN_ICONS` slot, and this resolves a name to the component the declaring plugin set.
 */

import type { ComponentType } from "react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";

/** Resolve an icon name `plugin`'s backend declared to the component `plugin` set for it, if any. */
export function resolvePluginIcon(
  plugin: string,
  name?: string | null,
): ComponentType<{ className?: string }> | undefined {
  if (!name) return undefined;
  const icon = PLUGIN_ICONS.get(plugin)?.find((item) => item.name === name)?.component;
  if (!icon && process.env.NODE_ENV !== "production") {
    console.warn(
      `No icon set for "${name}"; the "${plugin}" plugin must set it in PLUGIN_ICONS ` +
        `(lib/icons/slots.ts) from its icons.ts.`,
    );
  }
  return icon;
}
