"use client";

import PluginListItem from "@/components/settings/ListItem";
import { usePluginContext } from "@/lib/plugins/context";

export default function PluginsSettings() {
  const {
    userPlugins: plugins,
    loading,
    error,
    refreshPlugins,
    enablePlugin,
    disablePlugin,
    updatePluginConfig,
  } = usePluginContext();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-edly-gray-600">Loading plugins...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-edly-red-600">
        Failed to load plugins: {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-edly-gray-50">
      <div className="mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-edly-gray-900">My Plugins</h1>
          <p className="mt-2 text-sm text-edly-gray-600">
            View all your installed plugins in one place.
          </p>
        </div>

        {plugins.length > 0 ? (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            {plugins.map((plugin, index) => (
              <PluginListItem
                key={plugin.plugin_name}
                plugin={plugin}
                isLast={index === plugins.length - 1}
                onEnable={() => enablePlugin(plugin.plugin_name)}
                onDisable={() => disablePlugin(plugin.plugin_name)}
                onConfigChange={(config) =>
                  updatePluginConfig(plugin.plugin_name, config)
                }
                onRefresh={refreshPlugins}
              />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <p className="text-edly-gray-500">No plugins found</p>
          </div>
        )}
      </div>
    </div>
  );
}
