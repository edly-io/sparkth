"use client";

import { useState } from "react";
import { Unplug } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";
import { useAuth } from "@/lib/auth-context";
import SlackIcon from "../SlackIcon";
import { getAuthorizationUrl, disconnectSlack, type ConnectionStatus } from "@/lib/slack-api";

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

  const handleDisconnectConfirmed = async () => {
    if (!token) return;
    setConfirmOpen(false);
    setLoading(true);
    try {
      await disconnectSlack(token);
      onStatusChange();
    } catch (error) {
      onError(`Failed to disconnect: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
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
              loading={loading}
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

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disconnect Slack workspace?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Students will stop receiving bot replies until you reconnect.
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="error" size="sm" onClick={handleDisconnectConfirmed}>
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
