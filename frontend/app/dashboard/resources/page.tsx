"use client";

import { File as DefaultFileIcon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useIsPluginEnabled } from "@/lib/plugins/usePlugins";
import { Spinner } from "@/components/Spinner";
import GoogleDrive from "@/plugins/google-drive/GoogleDrive";

export default function ResourcesPage() {
  const { token } = useAuth();
  const { isEnabled: isDriveEnabled, loading } = useIsPluginEnabled(token, "google-drive");

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="mx-auto" />
      </div>
    );
  }

  if (!isDriveEnabled) {
    return (
      <div className="flex flex-col h-full bg-surface-variant/30">
        <div className="bg-card border-b border-border px-6 py-4">
          <h2 className="text-xl font-semibold text-foreground">Resources</h2>
          <p className="text-sm text-muted-foreground">
            All imported files from your connected plugins
          </p>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center">
            <DefaultFileIcon className="mx-auto h-16 w-16 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold text-foreground mb-1">No plugins connected</h3>
            <p className="text-sm text-muted-foreground">
              Enable a plugin from My Plugins to start importing resources
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <GoogleDrive />;
}
