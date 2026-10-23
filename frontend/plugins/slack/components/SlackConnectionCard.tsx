"use client";

import { useState } from "react";
import { Unplug } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/lib/auth-context";
import SlackIcon from "../SlackIcon";
import { getAuthorizationUrl, disconnectSlack, type ConnectionStatus } from "@/lib/slack";

interface SlackConnectionCardProps {
  status: ConnectionStatus | null;
  onStatusChange: () => void;
  onError: (message: string) => void;
}

export default function SlackConnectionCard({
  status,
  onStatusChange,
  onError,
}: SlackConnectionCardProps) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleConnect = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const url = await getAuthorizationUrl(token);
      window.location.href = url;
    } catch (error) {
      setLoading(false);
      onError(`Failed to connect: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const handleDisconnect = async () => {
    if (!token) throw new Error("not signed in");
    await disconnectSlack(token);
    setConfirmOpen(false);
    onStatusChange();
  };

  return (
    <>
      <Card variant="outlined" className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <SlackIcon className="h-10 w-10 shrink-0 text-foreground" />
            <div>
              <h3 className="text-base font-semibold text-foreground">Slack TA Bot</h3>
              <p className="text-sm text-muted-foreground">
                {status?.connected
                  ? `Connected to "${status.team_name ?? "Slack workspace"}"`
                  : "Not connected"}
              </p>
            </div>
          </div>

          {status?.connected ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmOpen(true)}
              className="border-error-300 text-error-600 hover:bg-error-50 dark:border-error-700 dark:text-error-400 dark:hover:bg-error-900/20"
            >
              <Unplug className="w-4 h-4 mr-1" aria-hidden="true" />
              Disconnect
            </Button>
          ) : (
            <Button variant="primary" size="sm" onClick={handleConnect} loading={loading}>
              Connect Slack
            </Button>
          )}
        </div>
      </Card>

      {confirmOpen && (
        <ConfirmDialog
          title="Disconnect Slack workspace?"
          description="Students will stop receiving bot replies until you reconnect."
          confirmLabel="Disconnect"
          pendingLabel="Disconnecting"
          cancelLabel="Cancel"
          errorMessage="Failed to disconnect Slack."
          onConfirm={handleDisconnect}
          onClose={() => setConfirmOpen(false)}
        />
      )}
    </>
  );
}
