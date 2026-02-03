import { ComponentType } from "react";

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

/**
 * Plugin metadata and capabilities
 */
export interface PluginMetadata {
  name: string;
  displayName: string;
  description?: string;
  version?: string;
  author?: string;
  isCore?: boolean;
  category?:
    | "integration"
    | "utility"
    | "communication"
    | "analytics"
    | "other";
  icon?: ComponentType<{ className?: string }>;
  tags?: string[];
}

export interface SecretFieldSchema {
  label: string;
  placeholder?: string;
  description?: string;
  required?: boolean;
  type?: "password" | "text";
}

export type SecretsSchema = Record<string, SecretFieldSchema>;

/**
 * Plugin sidebar configuration
 */
export interface PluginSidebarConfig {
  showInSidebar?: boolean;
  sidebarIcon?: ComponentType<{ className?: string }>;
  sidebarLabel?: string;
  sidebarOrder?: number;
}

/**
 * Complete plugin definition
 */
export interface PluginDefinition extends PluginMetadata, PluginSidebarConfig {
  /**
   * Lazy load the main plugin component
   * @returns Promise resolving to the component module
   */
  loadComponent: () => Promise<{
    default: ComponentType<PluginComponentProps>;
  }>;

  /**
   * Optional: Load a settings/config component for the plugin
   */
  loadSettingsComponent?: () => Promise<{
    default: ComponentType<PluginComponentProps>;
  }>;

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
 * Plugin state from the API
 */
export interface UserPluginState {
  description: string;
  plugin_name: string;
  enabled: boolean;
  config: Record<string, string>;
  is_core: boolean;
}

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
