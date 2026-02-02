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
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading plugins...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center text-error-600 dark:text-error-400 bg-background min-h-screen">
        Failed to load plugins: {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">My Plugins</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            View all your installed plugins in one place.
          </p>
        </div>

        {plugins.length > 0 ? (
          <div className="bg-card rounded-lg shadow-sm overflow-hidden border border-border">
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
          <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
            <p className="text-muted-foreground">No plugins found</p>
          </div>
        )}
      </div>
    </div>
  );
}
