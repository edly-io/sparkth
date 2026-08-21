import { ComponentType } from "react";
import type { Schema } from "@/lib/api";
import type { Locale } from "@/lib/i18n/config";

// ============================================================================
// Plugin Configuration Types
// ============================================================================

/**
 * Configuration field types supported by the plugin system
 */
export type ConfigFieldType =
  | "text"
  | "url"
  | "password"
  | "number"
  | "boolean"
  | "select"
  | "textarea";

/**
 * Schema definition for a single configuration field
 */
export interface ConfigFieldSchema {
  type: ConfigFieldType;
  label: string;
  description?: string;
  required?: boolean;
  defaultValue?: string | number | boolean;
  placeholder?: string;
  options?: Array<{ value: string; label: string }>;
  validate?: (value: unknown) => string | undefined;
}

/**
 * Schema for plugin configuration
 */
export interface ConfigSchema {
  [key: string]: ConfigFieldSchema;
}

/**
 * Runtime configuration values
 */
export interface PluginConfig {
  [key: string]: unknown;
}

// ============================================================================
// Plugin Route Types
// ============================================================================

/**
 * Defines a route provided by a plugin
 */
export interface PluginRoute {
  path: string;
  label: string;
  icon?: ComponentType<{ className?: string }>;
  showInNav?: boolean;
}

// ============================================================================
// Plugin Hooks & Context Types
// ============================================================================

/**
 * Context provided to plugin components
 */
export interface PluginContext {
  config: PluginConfig;
  token: string | null;
  updateConfig: (config: Partial<PluginConfig>) => Promise<void>;
  callApi: <T = unknown>(endpoint: string, options?: RequestInit) => Promise<T>;
}

/**
 * Props passed to the main plugin component
 */
export interface PluginComponentProps {
  config: PluginConfig;
  context?: PluginContext;
}

// ============================================================================
// Plugin Definition Types
// ============================================================================

export interface SecretFieldSchema {
  label: string;
  placeholder?: string;
  description?: string;
  required?: boolean;
  type?: "password" | "text";
}

export type SecretsSchema = Record<string, SecretFieldSchema>;

/**
 * Complete plugin definition.
 *
 * Holds only what the frontend alone can own: the plugin name and the
 * component loaders. Display name, description, icon, and sidebar config are
 * declared by the backend plugin and arrive on {@link UserPluginState} via
 * the user-plugins API (`display`, `sidebar`, `has_frontend`).
 */
export interface PluginDefinition {
  /** Plugin name, must match the backend plugin's declared name */
  name: string;

  /**
   * Lazy load the main plugin component
   * @returns Promise resolving to the component module
   */
  loadComponent: () => Promise<{
    default: ComponentType<PluginComponentProps>;
  }>;

  /**
   * Optional: Load a settings/config component for the plugin.
   * Settings components use their own prop contract (not PluginComponentProps),
   * so the return type is intentionally widened to ComponentType<any>.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  loadSettingsComponent?: () => Promise<{ default: ComponentType<any> }>;

  /**
   * Optional: Lazy load the plugin's message catalog for a locale.
   *
   * A plugin owns its catalogs: the files live under the plugin's own
   * `messages/` directory and the returned object must be scoped to a single
   * top-level namespace equal to the plugin name. `loadMessages` in
   * `lib/i18n/messages.ts` merges every registered plugin's catalog into the
   * core one at load time.
   */
  loadMessages?: (locale: Locale) => Promise<Record<string, unknown>>;

  /** Plugin routes */
  routes?: PluginRoute[];

  /** Configuration schema for the plugin */
  configSchema?: ConfigSchema;

  /**
   * Optional initialization function called when plugin is loaded
   */
  onInit?: (context: PluginContext) => void | Promise<void>;

  /**
   * Optional cleanup function called when plugin is unloaded
   */
  onDestroy?: () => void | Promise<void>;
}

// ============================================================================
// User Plugin State Types
// ============================================================================

/**
 * Represents a plugin's state for a specific user
 */
export interface EnabledPlugin {
  name: string;
  config: PluginConfig;
  enabled: boolean;
}

/**
 * The display info a backend plugin declared (DISPLAY_INFO hook).
 */
export type PluginDisplayInfo = Schema<"DisplayInfo">;

/**
 * The sidebar entry a backend plugin declared (SIDEBAR_ENTRIES hook).
 */
export type PluginSidebarEntry = Schema<"SidebarEntry">;

/**
 * Plugin state from the API, sourced from the generated schema so the shape
 * cannot drift from the backend response.
 *
 * `display`, `sidebar`, and `has_frontend` carry the read-only metadata the
 * backend plugin declared through the frontend hooks.
 */
export type UserPluginState = Schema<"UserPluginResponse">;

// ============================================================================
// Plugin Event Types
// ============================================================================

/**
 * Events that plugins can emit/listen to
 */
export type PluginEventType =
  | "plugin:enabled"
  | "plugin:disabled"
  | "plugin:config-updated"
  | "plugin:error";

export interface PluginEvent {
  type: PluginEventType;
  pluginName: string;
  payload?: unknown;
}

export type PluginEventHandler = (event: PluginEvent) => void;

// ============================================================================
// Plugin API Types
// ============================================================================

/**
 * Standard API response wrapper
 */
export interface PluginApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

/**
 * Plugin API client interface
 */
export interface PluginApiClient {
  get: <T = unknown>(endpoint: string) => Promise<T>;
  post: <T = unknown>(endpoint: string, data?: unknown) => Promise<T>;
  put: <T = unknown>(endpoint: string, data?: unknown) => Promise<T>;
  patch: <T = unknown>(endpoint: string, data?: unknown) => Promise<T>;
  delete: <T = unknown>(endpoint: string) => Promise<T>;
}
