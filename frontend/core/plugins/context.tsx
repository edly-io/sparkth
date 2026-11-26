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
import { api, ApiRequestError, bearer } from "@/lib/api";
import { isPluginUsable } from "./metadata";
import { PluginConfig, PluginContext as IPluginContext, PluginState } from "./types";

// ============================================================================
// Plugin Context Types
// ============================================================================

interface PluginProviderState {
  plugins: PluginState[];
  loading: boolean;
  error: string | null;
}

interface PluginContextValue extends PluginProviderState {
  refreshPlugins: () => Promise<void>;
  getPluginConfig: (pluginName: string) => PluginConfig;
  updatePluginConfig: (pluginName: string, config: Partial<PluginConfig>) => Promise<void>;
  enablePlugin: (pluginName: string) => Promise<void>;
  disablePlugin: (pluginName: string) => Promise<void>;
  isPluginUsableByName: (pluginName: string) => boolean;
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

// This module's public contract is plain Error objects; network failures
// propagate untouched.
function toError(prefix: string | null, error: unknown): never {
  if (error instanceof ApiRequestError) {
    throw new Error(prefix ? `${prefix}: ${error.message}` : error.message);
  }
  throw error;
}

async function fetchPlugins(token: string): Promise<PluginState[]> {
  try {
    const { data } = await api.GET("/api/v1/plugins/", { headers: bearer(token) });
    return data as PluginState[];
  } catch (error) {
    toError("Failed to fetch plugins", error);
  }
}

async function updatePluginConfigApi(
  pluginName: string,
  config: Record<string, unknown>,
  token: string,
): Promise<PluginState> {
  try {
    const { data } = await api.PUT("/api/v1/plugins/{plugin_name}/config", {
      params: { path: { plugin_name: pluginName } },
      body: { config },
      headers: bearer(token),
    });
    return data as PluginState;
  } catch (error) {
    toError(null, error);
  }
}

async function togglePluginApi(
  pluginName: string,
  action: "enable" | "disable",
  token: string,
): Promise<PluginState> {
  try {
    const options = {
      params: { path: { plugin_name: pluginName } },
      headers: bearer(token),
    };
    const { data } =
      action === "enable"
        ? await api.PATCH("/api/v1/plugins/{plugin_name}/enable", options)
        : await api.PATCH("/api/v1/plugins/{plugin_name}/disable", options);
    return data as PluginState;
  } catch (error) {
    toError(`Failed to ${action} plugin`, error);
  }
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
    plugins: [],
    loading: true,
    error: null,
  });

  const refreshPlugins = useCallback(async () => {
    if (!token) {
      setState((prev) => ({
        ...prev,
        loading: false,
        plugins: [],
      }));
      return;
    }

    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const plugins = await fetchPlugins(token);

      setState({
        plugins,
        loading: false,
        error: null,
      });
    } catch (error) {
      console.error("Failed to load plugins:", error);
      setState((prev) => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load plugins",
      }));
    }
  }, [token]);

  useEffect(() => {
    refreshPlugins();
  }, [refreshPlugins]);

  const getPluginConfig = useCallback(
    (pluginName: string): PluginConfig => {
      const plugin = state.plugins.find((p) => p.plugin_name === pluginName);
      return plugin?.config || {};
    },
    [state.plugins],
  );

  const updatePluginConfig = useCallback(
    async (pluginName: string, config: Partial<PluginConfig>) => {
      if (!token) throw new Error("Not authenticated");

      const currentConfig = getPluginConfig(pluginName);
      const newConfig = { ...currentConfig, ...config };

      await updatePluginConfigApi(pluginName, newConfig, token);
      await refreshPlugins();
    },
    [token, getPluginConfig, refreshPlugins],
  );

  const enablePlugin = useCallback(
    async (pluginName: string) => {
      if (!token) throw new Error("Not authenticated");

      await togglePluginApi(pluginName, "enable", token);
      await refreshPlugins();
    },
    [token, refreshPlugins],
  );

  const disablePlugin = useCallback(
    async (pluginName: string) => {
      if (!token) throw new Error("Not authenticated");

      await togglePluginApi(pluginName, "disable", token);
      await refreshPlugins();
    },
    [token, refreshPlugins],
  );

  const isPluginUsableByName = useCallback(
    (pluginName: string): boolean => {
      return state.plugins.some((p) => p.plugin_name === pluginName && isPluginUsable(p));
    },
    [state.plugins],
  );

  const createPluginContext = useCallback(
    (pluginName: string): IPluginContext => {
      const config = getPluginConfig(pluginName);

      return {
        config,
        token,
        updateConfig: (newConfig: Partial<PluginConfig>) =>
          updatePluginConfig(pluginName, newConfig),
        // Dynamic passthrough for arbitrary plugin endpoints: paths are built
        // at runtime, so they cannot be statically typed against the OpenAPI
        // schema. This is the one deliberate raw-fetch exception (issue #403).
        callApi: async <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
          const url = endpoint.startsWith("/")
            ? `${API_BASE}${endpoint}`
            : `${API_BASE}/${pluginName}/${endpoint}`;

          const response = await fetch(url, {
            ...options,
            headers: {
              "Content-Type": "application/json",
              ...(token ? bearer(token) : {}),
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
    [token, getPluginConfig, updatePluginConfig],
  );

  const contextValue = useMemo<PluginContextValue>(
    () => ({
      ...state,
      refreshPlugins,
      getPluginConfig,
      updatePluginConfig,
      enablePlugin,
      disablePlugin,
      isPluginUsableByName,
      createPluginContext,
    }),
    [
      state,
      refreshPlugins,
      getPluginConfig,
      updatePluginConfig,
      enablePlugin,
      disablePlugin,
      isPluginUsableByName,
      createPluginContext,
    ],
  );

  return <PluginContext.Provider value={contextValue}>{children}</PluginContext.Provider>;
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
 * Hook to get a specific plugin's context
 * @param pluginName - Name of the plugin
 */
export function usePlugin(pluginName: string): {
  /** The plugin is usable: on for the user and on system-wide. */
  isUsable: boolean;
  /** The user's plugins are still loading, so `isUsable` and `config` are not known yet. */
  loading: boolean;
  config: PluginConfig;
  context: IPluginContext;
  updateConfig: (config: Partial<PluginConfig>) => Promise<void>;
} {
  const {
    loading,
    isPluginUsableByName,
    getPluginConfig,
    createPluginContext,
    updatePluginConfig,
  } = usePluginContext();

  const isUsable = isPluginUsableByName(pluginName);
  const config = getPluginConfig(pluginName);
  const context = useMemo(() => createPluginContext(pluginName), [pluginName, createPluginContext]);

  return {
    isUsable,
    loading,
    config,
    context,
    updateConfig: (newConfig: Partial<PluginConfig>) => updatePluginConfig(pluginName, newConfig),
  };
}
