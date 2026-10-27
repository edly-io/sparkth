/**
 * The slot through which a plugin contributes its entry to the settings page.
 *
 * A plugin sets one `SettingsItem` under its name: the row the page lists it with and, when the
 * plugin has config, a loader for the modal that edits it. The page renders the item of every
 * plugin the API returns and passes it that plugin's state and actions, so it knows nothing about
 * any plugin itself.
 */

import type { ComponentType } from "react";

import type { UserPluginState } from "@/core/plugins/types";
import type { Slot } from "@/lib/slots";

export type ConfigFieldType = "string" | "integer" | "number" | "boolean" | "array";

/** One field of a plugin's config, read from the JSON schema the backend declares. */
export interface ConfigFieldDescriptor {
  name: string;
  label: string;
  description?: string;
  /** Name of the control that renders this field. */
  widget: string;
  type: ConfigFieldType;
  /** The schema lists the field in `required` — it has no default to fall back on. */
  required: boolean;
  /** The field accepts null, so leaving it unset is meaningful. */
  nullable: boolean;
  default?: unknown;
  minimum?: number;
  maximum?: number;
}

/** What a config modal passes to the control that renders a field. */
export interface ConfigWidgetProps {
  field: ConfigFieldDescriptor;
  value: unknown;
  /** Every field's current value, for a widget that depends on a sibling. */
  values: Record<string, unknown>;
  /** Every field, so a dependent widget can find its sibling by widget name. */
  fields: ConfigFieldDescriptor[];
  error?: string;
  disabled?: boolean;
  onChange: (name: string, value: unknown) => void;
}

/** What the settings page passes to a plugin's row. */
export interface SettingsListItemProps {
  plugin: UserPluginState;
  onEnable: () => Promise<void>;
  onDisable: () => Promise<void>;
  /**
   * Opens the plugin's config modal; absent when the plugin supplied none or its backend config
   * declares no fields.
   */
  onConfigure?: () => void;
}

/** What the settings page passes to a plugin's config modal. */
export interface ConfigModalProps {
  plugin: UserPluginState;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: Record<string, unknown>) => Promise<void>;
  onRefresh: () => void;
}

/** A plugin's entry on the settings page. */
export interface SettingsItem {
  listItem: ComponentType<SettingsListItemProps>;
  /** Loads the plugin's config modal, only when the user opens it. */
  loadConfigModal?: () => Promise<{ default: ComponentType<ConfigModalProps> }>;
}

/** Each plugin's settings entry, set by the plugin under its name. */
export const SETTINGS_ITEMS: Slot<SettingsItem> = new Map();
