"use client";

import { useState } from "react";
import { FolderSync, RefreshCw, Unplug } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import GoogleDriveIcon from "@/plugins/google-drive/GoogleDriveIcon";
import {
  getAuthorizationUrl,
  disconnectGoogle,
  ConnectionStatus as ConnectionStatusType,
} from "@/lib/drive";

interface ConnectionStatusProps {
  status: ConnectionStatusType | null;
  onStatusChange: () => void;
  onSyncFolder?: () => void;
  onResync?: () => void;
  resyncing?: boolean;
}

export default function ConnectionStatus({
  status,
  onStatusChange,
  onSyncFolder,
  onResync,
  resyncing,
}: ConnectionStatusProps) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    if (!token) return;

    setLoading(true);
    try {
      const url = await getAuthorizationUrl(token);
      window.location.href = url;
      // Keep loading=true — page will navigate to Google OAuth
    } catch (error) {
      setLoading(false);
      alert(`Failed to connect: ${error}`);
    }
  };

  const handleDisconnect = async () => {
    if (!token) return;
    if (!confirm("Are you sure you want to disconnect Google Drive?")) return;

    setLoading(true);
    try {
      await disconnectGoogle(token);
      onStatusChange();
    } catch (error) {
      alert(`Failed to disconnect: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card variant="outlined" className="p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <GoogleDriveIcon className="h-10 w-10 shrink-0" />
          <div>
            <h3 className="text-base font-semibold text-foreground">Google Drive</h3>
            <p className="text-sm text-muted-foreground">
              {status?.connected ? `Connected as ${status.email}` : "Not connected"}
            </p>
          </div>
        </div>

        {status?.connected ? (
          <div className="flex items-center gap-2">
            {onResync && (
              <Button variant="outline" size="sm" onClick={onResync} disabled={resyncing}>
                <RefreshCw className={`w-4 h-4 mr-1 ${resyncing ? "animate-spin" : ""}`} />
                Re-sync
              </Button>
            )}
            {onSyncFolder && (
              <Button variant="outline" size="sm" onClick={onSyncFolder}>
                <FolderSync className="w-4 h-4 mr-1" />
                Sync Folder
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleDisconnect}
              loading={loading}
              className="border-error-300 text-error-600 hover:bg-error-50 dark:border-error-700 dark:text-error-400 dark:hover:bg-error-900/20"
            >
              <Unplug className="w-4 h-4 mr-1" />
              Disconnect
            </Button>
          </div>
        ) : (
          <Button variant="primary" size="sm" onClick={handleConnect} loading={loading}>
            Connect Google Drive
          </Button>
        )}
      </div>
    </Card>
  );
}
