/**
 * Plugin icon resolution.
 *
 * The backend declares icons as names; each plugin sets the component for its names in the
 * `PLUGIN_ICONS` slot, and this resolves a declared name to that component.
 */

import type { ComponentType } from "react";

import { PLUGIN_ICONS } from "@/lib/icons/slots";
import { namedSlotItem } from "@/lib/slots";

/** Resolve an icon name from the API to the component a plugin set for it, if any. */
export function resolvePluginIcon(
  name?: string | null,
): ComponentType<{ className?: string }> | undefined {
  if (!name) return undefined;
  const icon = namedSlotItem(PLUGIN_ICONS, name)?.component;
  if (!icon && process.env.NODE_ENV !== "production") {
    console.warn(
      `No icon set for "${name}"; the plugin that declares it must set it in PLUGIN_ICONS ` +
        `(lib/icons/slots.ts) from its icons.ts.`,
    );
  }
  return icon;
}
