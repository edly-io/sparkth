"use client";

import { useState } from "react";
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
}

export default function ConnectionStatus({ status, onStatusChange }: ConnectionStatusProps) {
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
          <Button variant="outline" size="sm" onClick={handleDisconnect} loading={loading}>
            Disconnect
          </Button>
        ) : (
          <Button variant="primary" size="sm" onClick={handleConnect} loading={loading}>
            Connect Google Drive
          </Button>
        )}
      </div>
    </Card>
  );
}
