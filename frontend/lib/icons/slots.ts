/**
 * The slot through which a plugin ships the icons its backend declares.
 *
 * The backend declares a plugin's display and sidebar icons as names, such as a lucide icon name
 * or a brand name. The plugin sets the component for each of its names here, and core renders it.
 * A name belongs to the plugin that declares it, so two plugins can use the same name.
 */

import type { ComponentType } from "react";

import type { Slot } from "@/lib/slots";

/** An icon component, set under the name the backend declares. */
export interface PluginIcon {
  name: string;
  component: ComponentType<{ className?: string }>;
}

/** The icons each plugin set, looked up within the plugin that declares the name. */
export const PLUGIN_ICONS: Slot<PluginIcon> = new Map();
