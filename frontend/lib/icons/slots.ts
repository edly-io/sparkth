/**
 * The slot through which a plugin ships the icons its backend declares.
 *
 * The backend declares a plugin's display and sidebar icons as names, such as a lucide icon name
 * or a brand name. The plugin sets the component for each name here, and core renders it.
 */

import type { ComponentType } from "react";

import type { NamedSlot } from "@/lib/slots";

/** An icon component, set under the name the backend declares. */
export interface PluginIcon {
  name: string;
  component: ComponentType<{ className?: string }>;
}

/** The icons plugins set, looked up by name. */
export const PLUGIN_ICONS: NamedSlot<PluginIcon> = new Map();
