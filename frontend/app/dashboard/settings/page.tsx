"use client";

import { SettingsList } from "@/core/components/settings/SettingsList";
import { usePluginContext } from "@/core/plugins/context";
import { Spinner } from "@/core/components/ui/Spinner";

export default function PluginsSettings() {
  const { loading, error } = usePluginContext();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
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

        <SettingsList />
      </div>
    </div>
  );
}
