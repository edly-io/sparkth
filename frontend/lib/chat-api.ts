const API_BASE = "/api/v1/chat";

export interface ApiMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  message_type: "text" | "attachment";
  attachment_name: string | null;
  attachment_size: number | null;
  created_at: string;
  rag_sections: { type: string; name: string; source?: string }[] | null;
  tool_calls: { name: string }[] | null;
  is_error: boolean;
}

export interface ApiConversation {
  id: string;
  messages: ApiMessage[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface PersistedAttachment {
  id: number;
  name: string;
  size: number | null;
}

export interface OutgoingChatMessage {
  role: string;
  content: string | object[];
  attachment?: { name: string; size: number };
}

export interface ChatCompletionRequestBody {
  llm_config_id: number | undefined;
  model_override?: string;
  messages: OutgoingChatMessage[];
  stream: boolean;
  tools: string;
  tool_choice: string;
  include_system_tools_message: boolean;
  similarity_threshold: number;
  conversation_id?: string;
  drive_file_ids?: number[];
}

// Token may be null pre-login; the backend rejects "Bearer null" with 401,
// which callers already handle. Matches the previous inline behavior exactly.
function authHeaders(token: string | null): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function jsonAuthHeaders(token: string | null): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export async function requestChatCompletionStream(
  token: string | null,
  body: ChatCompletionRequestBody,
): Promise<Response> {
  return fetch(`${API_BASE}/completions`, {
    method: "POST",
    headers: jsonAuthHeaders(token),
    body: JSON.stringify(body),
  });
}

export async function getConversation(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<ApiConversation> {
  const r = await fetch(`${API_BASE}/conversations/${conversationId}`, {
    headers: authHeaders(token),
    signal,
  });
  if (!r.ok) throw new Error(`Load conversation failed with status ${r.status}`);
  return r.json();
}

export async function getConversationAttachments(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<PersistedAttachment[]> {
  const r = await fetch(`${API_BASE}/conversations/${conversationId}/attachments`, {
    headers: authHeaders(token),
    signal,
  });
  // Attachment-list failures are non-fatal: the conversation still renders.
  return r.ok ? r.json() : [];
}

export async function getLastMessage(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<ApiMessage | null> {
  const r = await fetch(`${API_BASE}/conversations/${conversationId}/last-message`, {
    headers: authHeaders(token),
    signal,
  });
  if (!r.ok) return null;
  return r.json();
}

export async function listConversations(
  token: string | null,
  signal?: AbortSignal,
): Promise<ConversationSummary[]> {
  const r = await fetch(`${API_BASE}/conversations`, {
    headers: authHeaders(token),
    signal,
  });
  if (!r.ok) throw new Error(`Failed to load conversations: HTTP ${r.status}`);
  const data = await r.json();
  return data.conversations ?? [];
}

export async function attachDriveFile(
  token: string | null,
  conversationId: string,
  driveFileId: number,
): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/attachments`, {
    method: "POST",
    headers: jsonAuthHeaders(token),
    body: JSON.stringify({ drive_file_id: driveFileId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function detachDriveFile(
  token: string | null,
  conversationId: string,
  driveFileDbId: number,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/conversations/${conversationId}/attachments/${driveFileDbId}`,
    {
      method: "DELETE",
      headers: authHeaders(token),
    },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
