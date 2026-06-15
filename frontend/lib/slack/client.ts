import { api, ApiRequestError } from "@/lib/api";
import type {
  AuthorizationUrlResponse,
  ConnectionStatus,
  FetchLogsOptions,
  LogsResponse,
  RagSourcesResponse,
} from "@/lib/slack/types";

function bearer(token: string): { Authorization: string } {
  return { Authorization: `Bearer ${token}` };
}

// This module's public contract is plain Error objects with action-prefixed
// messages; network failures propagate untouched.
function toError(prefix: string, error: unknown): never {
  if (error instanceof ApiRequestError) throw new Error(`${prefix}: ${error.message}`);
  throw error;
}

export async function getConnectionStatus(token: string): Promise<ConnectionStatus> {
  try {
    const { data } = await api.GET("/api/v1/slack/oauth/status", { headers: bearer(token) });
    return data as ConnectionStatus;
  } catch (error) {
    toError("Failed to fetch connection status", error);
  }
}

export async function getAuthorizationUrl(token: string): Promise<string> {
  try {
    const { data } = await api.GET("/api/v1/slack/oauth/authorize", { headers: bearer(token) });
    return (data as AuthorizationUrlResponse).url;
  } catch (error) {
    toError("Failed to get authorization URL", error);
  }
}

export async function disconnectSlack(token: string): Promise<void> {
  try {
    await api.DELETE("/api/v1/slack/oauth/disconnect", { headers: bearer(token) });
  } catch (error) {
    toError("Failed to disconnect Slack", error);
  }
}

export async function fetchLogs(token: string, opts: FetchLogsOptions): Promise<LogsResponse> {
  try {
    const { data } = await api.GET("/api/v1/slack/logs", {
      params: { query: { limit: opts.limit, cursor: opts.cursor, since_id: opts.sinceId } },
      headers: bearer(token),
    });
    return data as LogsResponse;
  } catch (error) {
    toError("Failed to fetch logs", error);
  }
}

export async function fetchRagSources(token: string): Promise<RagSourcesResponse> {
  try {
    const { data } = await api.GET("/api/v1/slack/rag/sources", { headers: bearer(token) });
    return data as RagSourcesResponse;
  } catch (error) {
    toError("Failed to fetch RAG sources", error);
  }
}
