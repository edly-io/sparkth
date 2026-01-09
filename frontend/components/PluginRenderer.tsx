"use client";

import { Suspense, lazy, useMemo, useEffect, useState } from "react";
import { PluginDefinition } from "@/lib/plugins/types";
import { usePlugin } from "@/lib/plugins/context";
import { emitPluginEvent } from "@/lib/plugins/registry";

interface PluginRendererProps {
  pluginName: string;
  pluginDef?: PluginDefinition;
}

function PluginErrorBoundary({
  children,
  pluginName,
}: {
  children: React.ReactNode;
  pluginName: string;
}) {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const errorHandler = (event: ErrorEvent) => {
      console.error(`Plugin "${pluginName}" error:`, event.error);
      setHasError(true);
      emitPluginEvent({
        type: "plugin:error",
        pluginName,
        payload: { error: event.error?.message || "Unknown error" },
      });
    };

    window.addEventListener("error", errorHandler);
    return () => window.removeEventListener("error", errorHandler);
  }, [pluginName]);

  if (hasError) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center max-w-md">
          <div className="text-red-600 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Plugin Error
          </h3>
          <p className="text-gray-600 mb-4">
            The plugin <strong>{pluginName}</strong> encountered an error and
            could not be loaded.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Reload Page
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

function PluginLoadingFallback({ displayName }: { displayName: string }) {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="text-center">
        <div className="relative w-16 h-16 mx-auto mb-4">
          <div className="absolute inset-0 border-4 border-gray-200 rounded-full"></div>
          <div className="absolute inset-0 border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
        </div>
        <p className="text-gray-600 font-medium">Loading {displayName}...</p>
        <p className="text-gray-400 text-sm mt-1">Please wait</p>
      </div>
    </div>
  );
}

export default function PluginRenderer({
  pluginName,
  pluginDef: overridePluginDef,
}: PluginRendererProps) {
  const { isEnabled, config, context } = usePlugin(pluginName);
  const [pluginDef, setPluginDef] = useState<PluginDefinition | null>(
    overridePluginDef || null
  );

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

  if (!pluginDef) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center">
          <p className="text-gray-600">
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
          <div className="text-gray-400 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Plugin Disabled
          </h3>
          <p className="text-gray-600">
            The plugin <strong>{pluginDef.displayName}</strong> is currently
            disabled.
          </p>
        </div>
      </div>
    );
  }

  if (!PluginComponent) {
    return <PluginLoadingFallback displayName={pluginDef.displayName} />;
  }

  return (
    <PluginErrorBoundary pluginName={pluginName}>
      <Suspense
        fallback={<PluginLoadingFallback displayName={pluginDef.displayName} />}
      >
        <PluginComponent config={config} context={context} />
      </Suspense>
    </PluginErrorBoundary>
  );
}
