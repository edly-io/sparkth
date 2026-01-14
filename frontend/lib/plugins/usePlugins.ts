import { useEffect, useState, useCallback, useMemo } from "react";
import { getPluginsByNames, PluginDefinition, onPluginEvent } from "./registry";
import { PluginConfig, UserPluginState, PluginEventType } from "./types";
import { fetchUserPlugins } from "./context";

// ============================================================================
// Types
// ============================================================================

interface UsePluginsResult {
  enabledPlugins: PluginDefinition[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

interface UsePluginResult {
  plugin: PluginDefinition | undefined;
  config: PluginConfig;
  isEnabled: boolean;
  loading: boolean;
  error: string | null;
}

interface UseSidebarPluginsResult {
  plugins: PluginDefinition[];
  loading: boolean;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch and manage user's enabled plugins
 * @param token - Authentication token
 * @returns Object containing enabled plugins, loading state, and refresh function
 */
export function usePlugins(token: string | null): UsePluginsResult {
  const [enabledPlugins, setEnabledPlugins] = useState<PluginDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPlugins = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setEnabledPlugins([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const userPlugins = await fetchUserPlugins(token);
      const enabledNames = userPlugins
        .filter((p) => p.enabled)
        .map((p) => p.plugin_name);

      const plugins = getPluginsByNames(enabledNames);
      setEnabledPlugins(plugins);
    } catch (err) {
      console.error("Failed to load plugins:", err);
      setError(err instanceof Error ? err.message : "Failed to load plugins");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPlugins();
  }, [loadPlugins]);

  useEffect(() => {
    const unsubscribeEnabled = onPluginEvent("plugin:enabled", () => {
      loadPlugins();
    });
    const unsubscribeDisabled = onPluginEvent("plugin:disabled", () => {
      loadPlugins();
    });

    return () => {
      unsubscribeEnabled();
      unsubscribeDisabled();
    };
  }, [loadPlugins]);

  return {
    enabledPlugins,
    loading,
    error,
    refresh: loadPlugins,
  };
}

/**
 * Hook to get a specific plugin's state
 * @param token - Authentication token
 * @param pluginName - Name of the plugin
 * @returns Plugin state including definition, config, and enabled status
 */
export function usePluginState(
  token: string | null,
  pluginName: string
): UsePluginResult {
  const [state, setState] = useState<{
    config: PluginConfig;
    isEnabled: boolean;
    loading: boolean;
    error: string | null;
  }>({
    config: {},
    isEnabled: false,
    loading: true,
    error: null,
  });

  const plugin = useMemo(() => {
    const plugins = getPluginsByNames([pluginName]);
    return plugins[0];
  }, [pluginName]);

  useEffect(() => {
    async function loadPluginState() {
      if (!token) {
        setState((prev) => ({ ...prev, loading: false }));
        return;
      }

      try {
        const userPlugins = await fetchUserPlugins(token);
        const userPlugin = userPlugins.find(
          (p) => p.plugin_name === pluginName
        );

        setState({
          config: userPlugin?.config || {},
          isEnabled: userPlugin?.enabled || false,
          loading: false,
          error: null,
        });
      } catch (err) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load plugin",
        }));
      }
    }

    loadPluginState();
  }, [token, pluginName]);

  useEffect(() => {
    const unsubscribe = onPluginEvent("plugin:config-updated", (event) => {
      if (event.pluginName === pluginName && event.payload) {
        setState((prev) => ({
          ...prev,
          config: event.payload as PluginConfig,
        }));
      }
    });

    return unsubscribe;
  }, [pluginName]);

  return {
    plugin,
    ...state,
  };
}

/**
 * Hook to get plugins for sidebar navigation
 * @param token - Authentication token
 * @returns Sidebar plugins sorted by order
 */
export function useSidebarPlugins(
  token: string | null
): UseSidebarPluginsResult {
  const { enabledPlugins, loading } = usePlugins(token);

  const sidebarPlugins = useMemo(() => {
    return enabledPlugins
      .filter((p) => p.showInSidebar)
      .sort((a, b) => (a.sidebarOrder || 99) - (b.sidebarOrder || 99));
  }, [enabledPlugins]);

  return {
    plugins: sidebarPlugins,
    loading,
  };
}

/**
 * Hook to check if a specific plugin is enabled
 * @param token - Authentication token
 * @param pluginName - Name of the plugin
 * @returns Boolean indicating if plugin is enabled
 */
export function useIsPluginEnabled(
  token: string | null,
  pluginName: string
): { isEnabled: boolean; loading: boolean } {
  const { enabledPlugins, loading } = usePlugins(token);

  const isEnabled = useMemo(() => {
    return enabledPlugins.some((p) => p.name === pluginName);
  }, [enabledPlugins, pluginName]);

  return { isEnabled, loading };
}

/**
 * Hook to get all user plugins (enabled and disabled)
 * @param token - Authentication token
 * @returns All user plugins with their states
 */
export function useAllUserPlugins(token: string | null): {
  plugins: UserPluginState[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [plugins, setPlugins] = useState<UserPluginState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPlugins = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setPlugins([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const userPlugins = await fetchUserPlugins(token);
      setPlugins(userPlugins);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plugins");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadPlugins();
  }, [loadPlugins]);

  return {
    plugins,
    loading,
    error,
    refresh: loadPlugins,
  };
}

/**
 * Hook to subscribe to plugin events
 * @param eventType - Type of event to listen for
 * @param handler - Event handler function
 */
export function usePluginEvent(
  eventType: PluginEventType,
  handler: (event: {
    type: PluginEventType;
    pluginName: string;
    payload?: unknown;
  }) => void
): void {
  useEffect(() => {
    const unsubscribe = onPluginEvent(eventType, handler);
    return unsubscribe;
  }, [eventType, handler]);
}
