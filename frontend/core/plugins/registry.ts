import { PluginDefinition, PluginEvent, PluginEventHandler, PluginEventType } from "./types";

// ============================================================================
// Plugin Registry - Singleton pattern for managing plugin registrations
// ============================================================================

class PluginRegistry {
  private plugins = new Map<string, PluginDefinition>();
  private eventHandlers = new Map<PluginEventType, Set<PluginEventHandler>>();
  private initialized = false;

  /**
   * Register a plugin definition
   * @param plugin - The plugin definition to register
   * @throws Error if plugin with same name already exists
   */
  register(plugin: PluginDefinition): void {
    if (this.plugins.has(plugin.name)) {
      console.warn(
        `Plugin "${plugin.name}" is already registered. Skipping duplicate registration.`,
      );
      return;
    }

    if (!plugin.name || !plugin.loadComponent) {
      throw new Error(`Invalid plugin definition: name and loadComponent are required`);
    }

    if (!/^[a-z][a-z0-9-]*$/.test(plugin.name)) {
      throw new Error(
        `Invalid plugin name "${plugin.name}". Must be kebab-case (e.g., "my-plugin")`,
      );
    }

    this.plugins.set(plugin.name, plugin);
    console.debug(`Plugin "${plugin.name}" registered successfully`);
  }

  /**
   * Unregister a plugin by name
   * @param name - Plugin name to unregister
   */
  unregister(name: string): boolean {
    const plugin = this.plugins.get(name);
    if (plugin) {
      if (plugin.onDestroy) {
        try {
          plugin.onDestroy();
        } catch (error) {
          console.error(`Error during plugin "${name}" cleanup:`, error);
        }
      }
      this.plugins.delete(name);
      return true;
    }
    return false;
  }

  /**
   * Get a plugin by name
   * @param name - Plugin name
   * @returns Plugin definition or undefined
   */
  get(name: string): PluginDefinition | undefined {
    return this.plugins.get(name);
  }

  /**
   * Get all registered plugins
   * @returns Array of all plugin definitions
   */
  getAll(): PluginDefinition[] {
    return Array.from(this.plugins.values());
  }

  /**
   * Get plugins by their names
   * @param names - Array of plugin names
   * @returns Array of found plugin definitions
   */
  getByNames(names: string[]): PluginDefinition[] {
    return names
      .map((name) => this.plugins.get(name))
      .filter((plugin): plugin is PluginDefinition => plugin !== undefined);
  }

  /**
   * Check if a plugin is registered
   * @param name - Plugin name
   * @returns boolean
   */
  has(name: string): boolean {
    return this.plugins.has(name);
  }

  /**
   * Get the count of registered plugins
   */
  get count(): number {
    return this.plugins.size;
  }

  // ===========================================================================
  // Event System
  // ===========================================================================

  /**
   * Subscribe to plugin events
   * @param eventType - Event type to listen for
   * @param handler - Event handler function
   * @returns Unsubscribe function
   */
  on(eventType: PluginEventType, handler: PluginEventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.eventHandlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * Emit a plugin event
   * @param event - Event to emit
   */
  emit(event: PluginEvent): void {
    const handlers = this.eventHandlers.get(event.type);
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(event);
        } catch (error) {
          console.error(`Error in plugin event handler for "${event.type}":`, error);
        }
      });
    }
  }

  /**
   * Clear all registered plugins (useful for testing)
   */
  clear(): void {
    this.plugins.clear();
    this.eventHandlers.clear();
    this.initialized = false;
  }

  /**
   * Mark registry as initialized
   */
  markInitialized(): void {
    this.initialized = true;
  }

  /**
   * Check if registry is initialized
   */
  isInitialized(): boolean {
    return this.initialized;
  }
}

// ============================================================================
// Singleton Instance & Exports
// ============================================================================

const registry = new PluginRegistry();

export function registerPlugin(plugin: PluginDefinition): void {
  registry.register(plugin);
}

export function unregisterPlugin(name: string): boolean {
  return registry.unregister(name);
}

export function getPlugin(name: string): PluginDefinition | undefined {
  return registry.get(name);
}

export function getAllPlugins(): PluginDefinition[] {
  return registry.getAll();
}

export function getPluginsByNames(names: string[]): PluginDefinition[] {
  return registry.getByNames(names);
}

export function hasPlugin(name: string): boolean {
  return registry.has(name);
}

export function onPluginEvent(eventType: PluginEventType, handler: PluginEventHandler): () => void {
  return registry.on(eventType, handler);
}

export function emitPluginEvent(event: PluginEvent): void {
  registry.emit(event);
}

export { registry as pluginRegistry };
export type { PluginDefinition };
