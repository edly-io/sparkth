"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from "react";
import {
  PluginDefinition,
  PluginConfig,
  PluginContext as IPluginContext,
  UserPluginState,
} from "./types";
import { getPluginsByNames, emitPluginEvent } from "./registry";

// ============================================================================
// Plugin Context Types
// ============================================================================

interface PluginProviderState {
  userPlugins: UserPluginState[];
  enabledPlugins: PluginDefinition[];
  loading: boolean;
  error: string | null;
}

interface PluginContextValue extends PluginProviderState {
  refreshPlugins: () => Promise<void>;
  getPluginConfig: (pluginName: string) => PluginConfig;
  updatePluginConfig: (
    pluginName: string,
    config: Partial<PluginConfig>
  ) => Promise<void>;
  enablePlugin: (pluginName: string) => Promise<void>;
  disablePlugin: (pluginName: string) => Promise<void>;
  isPluginEnabled: (pluginName: string) => boolean;
  createPluginContext: (pluginName: string) => IPluginContext;
}

// ============================================================================
// Context Creation
// ============================================================================

const PluginContext = createContext<PluginContextValue | undefined>(undefined);

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = "/api/v1";

async function fetchUserPlugins(token: string): Promise<UserPluginState[]> {
  const response = await fetch(`${API_BASE}/user-plugins/`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch plugins: ${text}`);
  }

  return response.json();
}

async function updatePluginConfigApi(
  pluginName: string,
  config: Record<string, unknown>,
  token: string
): Promise<UserPluginState> {
  const response = await fetch(
    `${API_BASE}/user-plugins/${pluginName}/config`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
      body: JSON.stringify({ config }),
    }
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update config: ${text}`);
  }

  return response.json();
}

async function togglePluginApi(
  pluginName: string,
  action: "enable" | "disable",
  token: string
): Promise<UserPluginState> {
  const response = await fetch(
    `${API_BASE}/user-plugins/${pluginName}/${action}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to ${action} plugin: ${text}`);
  }

  return response.json();
}

// ============================================================================
// Plugin Provider Component
// ============================================================================

interface PluginProviderProps {
  children: ReactNode;
  token: string | null;
}

export function PluginProvider({ children, token }: PluginProviderProps) {
  const [state, setState] = useState<PluginProviderState>({
    userPlugins: [],
    enabledPlugins: [],
    loading: true,
    error: null,
  });

  const refreshPlugins = useCallback(async () => {
    if (!token) {
      setState((prev) => ({
        ...prev,
        loading: false,
        userPlugins: [],
        enabledPlugins: [],
      }));
      return;
    }

    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const userPlugins = await fetchUserPlugins(token);
      const enabledNames = userPlugins
        .filter((p) => p.enabled)
        .map((p) => p.plugin_name);
      const enabledPlugins = getPluginsByNames(enabledNames);

      setState({
        userPlugins,
        enabledPlugins,
        loading: false,
        error: null,
      });
    } catch (error) {
      console.error("Failed to load plugins:", error);
      setState((prev) => ({
        ...prev,
        loading: false,
        error:
          error instanceof Error ? error.message : "Failed to load plugins",
      }));
    }
  }, [token]);

  useEffect(() => {
    refreshPlugins();
  }, [refreshPlugins]);

  const getPluginConfig = useCallback(
    (pluginName: string): PluginConfig => {
      const plugin = state.userPlugins.find(
        (p) => p.plugin_name === pluginName
      );
      return plugin?.config || {};
    },
    [state.userPlugins]
  );

  const updatePluginConfig = useCallback(
    async (pluginName: string, config: Partial<PluginConfig>) => {
      if (!token) throw new Error("Not authenticated");

      const currentConfig = getPluginConfig(pluginName);
      const newConfig = { ...currentConfig, ...config };

      await updatePluginConfigApi(pluginName, newConfig, token);

      emitPluginEvent({
        type: "plugin:config-updated",
        pluginName,
        payload: newConfig,
      });

      await refreshPlugins();
    },
    [token, getPluginConfig, refreshPlugins]
  );

  const enablePlugin = useCallback(
    async (pluginName: string) => {
      if (!token) throw new Error("Not authenticated");

      await togglePluginApi(pluginName, "enable", token);

      emitPluginEvent({
        type: "plugin:enabled",
        pluginName,
      });

      await refreshPlugins();
    },
    [token, refreshPlugins]
  );

  const disablePlugin = useCallback(
    async (pluginName: string) => {
      if (!token) throw new Error("Not authenticated");

      await togglePluginApi(pluginName, "disable", token);

      emitPluginEvent({
        type: "plugin:disabled",
        pluginName,
      });

      await refreshPlugins();
    },
    [token, refreshPlugins]
  );

  const isPluginEnabled = useCallback(
    (pluginName: string): boolean => {
      return state.userPlugins.some(
        (p) => p.plugin_name === pluginName && p.enabled
      );
    },
    [state.userPlugins]
  );

  const createPluginContext = useCallback(
    (pluginName: string): IPluginContext => {
      const config = getPluginConfig(pluginName);

      return {
        config,
        token,
        updateConfig: (newConfig: Partial<PluginConfig>) =>
          updatePluginConfig(pluginName, newConfig),
        callApi: async <T = unknown,>(
          endpoint: string,
          options?: RequestInit
        ): Promise<T> => {
          const url = endpoint.startsWith("/")
            ? `${API_BASE}${endpoint}`
            : `${API_BASE}/${pluginName}/${endpoint}`;

          const response = await fetch(url, {
            ...options,
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
              ...options?.headers,
            },
          });

          if (!response.ok) {
            const text = await response.text();
            throw new Error(`API call failed: ${text}`);
          }

          return response.json();
        },
      };
    },
    [token, getPluginConfig, updatePluginConfig]
  );

  const contextValue = useMemo<PluginContextValue>(
    () => ({
      ...state,
      refreshPlugins,
      getPluginConfig,
      updatePluginConfig,
      enablePlugin,
      disablePlugin,
      isPluginEnabled,
      createPluginContext,
    }),
    [
      state,
      refreshPlugins,
      getPluginConfig,
      updatePluginConfig,
      enablePlugin,
      disablePlugin,
      isPluginEnabled,
      createPluginContext,
    ]
  );

  return (
    <PluginContext.Provider value={contextValue}>
      {children}
    </PluginContext.Provider>
  );
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to access the plugin context
 * @throws Error if used outside PluginProvider
 */
export function usePluginContext(): PluginContextValue {
  const context = useContext(PluginContext);
  if (!context) {
    throw new Error("usePluginContext must be used within a PluginProvider");
  }
  return context;
}

/**
 * Hook to get enabled plugins
 */
export function useEnabledPlugins(): {
  plugins: PluginDefinition[];
  loading: boolean;
  error: string | null;
} {
  const { enabledPlugins, loading, error } = usePluginContext();
  return { plugins: enabledPlugins, loading, error };
}

/**
 * Hook to get a specific plugin's context
 * @param pluginName - Name of the plugin
 */
export function usePlugin(pluginName: string): {
  isEnabled: boolean;
  config: PluginConfig;
  context: IPluginContext;
  updateConfig: (config: Partial<PluginConfig>) => Promise<void>;
} {
  const {
    isPluginEnabled,
    getPluginConfig,
    createPluginContext,
    updatePluginConfig,
  } = usePluginContext();

  const isEnabled = isPluginEnabled(pluginName);
  const config = getPluginConfig(pluginName);
  const context = createPluginContext(pluginName);

  return {
    isEnabled,
    config,
    context,
    updateConfig: (newConfig: Partial<PluginConfig>) =>
      updatePluginConfig(pluginName, newConfig),
  };
}
