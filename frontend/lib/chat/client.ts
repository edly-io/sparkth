import type {
  ApiConversation,
  ApiMessage,
  ChatCompletionRequestBody,
  ConversationSummary,
  PersistedAttachment,
} from "@/lib/chat/types";

const API_BASE = "/api/v1/chat";

// NOTE: chat endpoints throw plain `Error` on failure, while `@/lib/api`
// and `@/lib/llm` throw the structured `ApiRequestError`. The chat plugin's
// callers only need a message, so the lighter contract is intentional for
// now. Aligning the two is tracked as a follow-up.

// TODO: tighten the signature to `token: string` once every caller has a
// guaranteed-non-null token. The backend rejects "Bearer null" with 401,
// but a literal "null" is still a silent bug magnet for new callers.
function authHeaders(token: string | null): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function jsonAuthHeaders(token: string | null): HeadersInit {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function chatFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    // Aborts are flow control, not failures: let callers see them as-is.
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    const message = error instanceof Error ? error.message : "Unknown error";
    throw new Error(`Network error: ${message}`);
  }
}

export async function requestChatCompletionStream(
  token: string | null,
  body: ChatCompletionRequestBody,
): Promise<Response> {
  return chatFetch(`${API_BASE}/completions`, {
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
  const r = await chatFetch(`${API_BASE}/conversations/${conversationId}`, {
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
  const r = await chatFetch(`${API_BASE}/conversations/${conversationId}/attachments`, {
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
  const r = await chatFetch(`${API_BASE}/conversations/${conversationId}/last-message`, {
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
  const r = await chatFetch(`${API_BASE}/conversations`, {
    headers: authHeaders(token),
    signal,
  });
  if (!r.ok) throw new Error(`Failed to load conversations: HTTP ${r.status}`);
  const data = await r.json();
  return data.conversations ?? [];
}

export async function attachDocument(
  token: string | null,
  conversationId: string,
  documentId: number,
): Promise<void> {
  const res = await chatFetch(`${API_BASE}/conversations/${conversationId}/attachments`, {
    method: "POST",
    headers: jsonAuthHeaders(token),
    body: JSON.stringify({ document_id: documentId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function detachDocument(
  token: string | null,
  conversationId: string,
  documentId: number,
): Promise<void> {
  const res = await chatFetch(
    `${API_BASE}/conversations/${conversationId}/attachments/${documentId}`,
    {
      method: "DELETE",
      headers: authHeaders(token),
    },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
