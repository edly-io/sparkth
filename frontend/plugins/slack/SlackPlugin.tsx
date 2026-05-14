"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { getConnectionStatus, type ConnectionStatus } from "@/lib/slack-api";
import SlackConnectionCard from "./components/SlackConnectionCard";
import { SLACK_PLUGIN_PATH } from "./index";

export default function SlackPlugin() {
  const { token } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [justConnected, setJustConnected] = useState(false);

  const loadStatus = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const s = await getConnectionStatus(token);
      setStatus(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Slack status");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (searchParams?.get("connected") === "true") {
      setJustConnected(true);
      router.replace(SLACK_PLUGIN_PATH);
      const timer = setTimeout(() => setJustConnected(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [searchParams, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-surface-variant/30">
      <div className="bg-card border-b border-border px-6 py-4">
        <h2 className="text-xl font-semibold text-foreground">Slack TA Bot</h2>
        <p className="text-sm text-muted-foreground">
          Connect your Slack workspace and answer student questions automatically
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {justConnected && <Alert severity="success">Connected to Slack.</Alert>}

        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <SlackConnectionCard status={status} onStatusChange={loadStatus} onError={setError} />
      </div>
    </div>
  );
}
