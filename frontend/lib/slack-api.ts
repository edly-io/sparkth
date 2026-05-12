const API_BASE = "/api/v1/slack";

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    Accept: "application/json",
  };
}

async function parseDetail(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const json = JSON.parse(text);
    return typeof json.detail === "string" ? json.detail : text;
  } catch {
    return text;
  }
}

export interface ConnectionStatus {
  connected: boolean;
  team_name: string | null;
  team_id: string | null;
  bot_user_id: string | null;
  connected_at: string | null;
}

export interface BotResponseLogItem {
  id: number;
  slack_channel: string;
  slack_user: string;
  question: string;
  answer: string | null;
  rag_matched: boolean;
  created_at: string;
}

export interface LogsResponse {
  items: BotResponseLogItem[];
  total: number;
  next_cursor: number | null;
  has_more: boolean;
}

export interface RagSourcesResponse {
  sources: string[];
}

export interface FetchLogsOptions {
  limit?: number;
  cursor?: number;
  sinceId?: number;
}

export async function getConnectionStatus(token: string): Promise<ConnectionStatus> {
  const res = await fetch(`${API_BASE}/oauth/status`, {
    method: "GET",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to fetch connection status: ${await parseDetail(res)}`);
  return res.json();
}

export async function getAuthorizationUrl(token: string): Promise<string> {
  const res = await fetch(`${API_BASE}/oauth/authorize`, {
    method: "GET",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to get authorization URL: ${await parseDetail(res)}`);
  const data = await res.json();
  return data.url as string;
}

export async function disconnectSlack(token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/oauth/disconnect`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to disconnect Slack: ${await parseDetail(res)}`);
}

export async function fetchLogs(token: string, opts: FetchLogsOptions): Promise<LogsResponse> {
  const params = new URLSearchParams();
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  if (opts.cursor !== undefined) params.set("cursor", String(opts.cursor));
  if (opts.sinceId !== undefined) params.set("since_id", String(opts.sinceId));

  const qs = params.toString();
  const url = qs ? `${API_BASE}/logs?${qs}` : `${API_BASE}/logs`;
  const res = await fetch(url, { method: "GET", headers: authHeaders(token) });
  if (!res.ok) throw new Error(`Failed to fetch logs: ${await parseDetail(res)}`);
  return res.json();
}

export async function fetchRagSources(token: string): Promise<RagSourcesResponse> {
  const res = await fetch(`${API_BASE}/rag/sources`, {
    method: "GET",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to fetch RAG sources: ${await parseDetail(res)}`);
  return res.json();
}
