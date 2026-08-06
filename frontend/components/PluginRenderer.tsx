"use client";

import { Suspense, lazy, useMemo, useEffect, useState } from "react";
import { Spinner } from "@/components/Spinner";
import { PluginDefinition, displayNameOf, emitPluginEvent } from "@/lib/plugins";
import { usePlugin, usePluginContext } from "@/lib/plugins/context";
import { PluginErrorBoundary } from "./PluginErrorBoundary";

interface PluginRendererProps {
  pluginName: string;
  pluginDef?: PluginDefinition;
}

function PluginLoadingFallback({ displayName }: { displayName: string }) {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="text-center">
        <Spinner className="mx-auto mb-4" />
        <p className="text-muted-foreground font-medium">Loading {displayName}...</p>
        <p className="text-muted text-sm mt-1">Please wait</p>
      </div>
    </div>
  );
}

export default function PluginRenderer({
  pluginName,
  pluginDef: overridePluginDef,
}: PluginRendererProps) {
  const { isEnabled, config, context } = usePlugin(pluginName);
  const { userPlugins, loading: pluginsLoading } = usePluginContext();
  const [pluginDef, setPluginDef] = useState<PluginDefinition | null>(overridePluginDef || null);

  const userPlugin = userPlugins.find((p) => p.plugin_name === pluginName);
  const displayName = userPlugin ? displayNameOf(userPlugin) : pluginName;

  useEffect(() => {
    if (overridePluginDef) {
      setPluginDef(overridePluginDef);
      return;
    }

    import("@/lib/plugins/registry").then(({ getPlugin }) => {
      const def = getPlugin(pluginName);
      if (def) {
        setPluginDef(def);
      } else {
        console.error(`Plugin "${pluginName}" not found in registry`);
      }
    });
  }, [pluginName, overridePluginDef]);

  useEffect(() => {
    if (pluginDef?.onInit && isEnabled) {
      const init = async () => {
        try {
          await pluginDef.onInit?.(context);
        } catch (error) {
          console.error(`Plugin "${pluginName}" initialization error:`, error);
          emitPluginEvent({
            type: "plugin:error",
            pluginName,
            payload: {
              error: error instanceof Error ? error.message : "Init failed",
            },
          });
        }
      };
      init();
    }

    return () => {
      if (pluginDef?.onDestroy) {
        try {
          pluginDef.onDestroy();
        } catch (error) {
          console.error(`Plugin "${pluginName}" cleanup error:`, error);
        }
      }
    };
  }, [pluginDef, pluginName, isEnabled, context]);

  const PluginComponent = useMemo(() => {
    if (!pluginDef) return null;
    return lazy(() => pluginDef.loadComponent());
  }, [pluginDef]);

  // Until the plugin list loads, neither isEnabled nor displayName is
  // meaningful, so don't render a verdict yet.
  if (pluginsLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Spinner />
      </div>
    );
  }

  if (!pluginDef) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center">
          <p className="text-muted-foreground">
            Plugin <strong>{pluginName}</strong> not found
          </p>
        </div>
      </div>
    );
  }

  if (!isEnabled) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center max-w-md">
          <div className="text-muted mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">Plugin Disabled</h3>
          <p className="text-muted-foreground">
            The plugin <strong>{displayName}</strong> is currently disabled.
          </p>
        </div>
      </div>
    );
  }

  if (!PluginComponent) {
    return <PluginLoadingFallback displayName={displayName} />;
  }

  return (
    <PluginErrorBoundary pluginName={pluginName}>
      <Suspense fallback={<PluginLoadingFallback displayName={displayName} />}>
        <PluginComponent config={config} context={context} />
      </Suspense>
    </PluginErrorBoundary>
  );
}
