import { api, ApiRequestError } from "@/lib/api";
import type {
  ApiConversation,
  ApiMessage,
  ChatCompletionRequestBody,
  ConversationSummary,
  PersistedAttachment,
} from "@/lib/chat/types";

// NOTE: chat endpoints throw plain `Error` on failure, while `@/lib/api`
// and `@/lib/llm` throw the structured `ApiRequestError`. The chat plugin's
// callers only need a message, so the lighter contract is intentional for
// now (requestChatCompletionStream is the exception: its caller branches on
// the structured error). Aligning the rest is tracked as a follow-up.

// TODO: tighten the signature to `token: string` once every caller has a
// guaranteed-non-null token. The backend rejects "Bearer null" with 401,
// but a literal "null" is still a silent bug magnet for new callers.
function authHeader(token: string | null): { Authorization: string } {
  return { Authorization: `Bearer ${token}` };
}

// Aborts are flow control; ApiRequestError is the middleware's typed failure
// (rethrown for callers that map or branch on it); anything else is transport.
function passOrWrapNetworkError(error: unknown): never {
  if (error instanceof DOMException && error.name === "AbortError") throw error;
  if (error instanceof ApiRequestError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new Error(`Network error: ${message}`);
}

export async function requestChatCompletionStream(
  token: string | null,
  body: ChatCompletionRequestBody,
): Promise<Response> {
  try {
    const { response } = await api.POST("/api/v1/chat/completions", {
      body,
      parseAs: "stream",
      headers: authHeader(token),
    });
    return response;
  } catch (error) {
    passOrWrapNetworkError(error);
  }
}

export async function getConversation(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<ApiConversation> {
  try {
    const { data } = await api.GET("/api/v1/chat/conversations/{conversation_id}", {
      params: { path: { conversation_id: conversationId } },
      headers: authHeader(token),
      signal,
    });
    return data as unknown as ApiConversation;
  } catch (error) {
    if (error instanceof ApiRequestError) {
      throw new Error(`Load conversation failed with status ${error.status}`);
    }
    passOrWrapNetworkError(error);
  }
}

export async function getConversationAttachments(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<PersistedAttachment[]> {
  try {
    const { data } = await api.GET("/api/v1/chat/conversations/{conversation_id}/attachments", {
      params: { path: { conversation_id: conversationId } },
      headers: authHeader(token),
      signal,
    });
    return data as PersistedAttachment[];
  } catch (error) {
    // Attachment-list failures are non-fatal: the conversation still renders.
    if (error instanceof ApiRequestError) return [];
    passOrWrapNetworkError(error);
  }
}

export async function getLastMessage(
  token: string | null,
  conversationId: string,
  signal?: AbortSignal,
): Promise<ApiMessage | null> {
  try {
    const { data } = await api.GET("/api/v1/chat/conversations/{conversation_id}/last-message", {
      params: { path: { conversation_id: conversationId } },
      headers: authHeader(token),
      signal,
    });
    return data as unknown as ApiMessage | null;
  } catch (error) {
    if (error instanceof ApiRequestError) return null;
    passOrWrapNetworkError(error);
  }
}

export async function listConversations(
  token: string | null,
  signal?: AbortSignal,
): Promise<ConversationSummary[]> {
  try {
    const { data } = await api.GET("/api/v1/chat/conversations", {
      headers: authHeader(token),
      signal,
    });
    return data?.conversations ?? [];
  } catch (error) {
    if (error instanceof ApiRequestError) {
      throw new Error(`Failed to load conversations: HTTP ${error.status}`);
    }
    passOrWrapNetworkError(error);
  }
}

export async function attachDocument(
  token: string | null,
  conversationId: string,
  documentId: number,
): Promise<void> {
  try {
    await api.POST("/api/v1/chat/conversations/{conversation_id}/attachments", {
      params: { path: { conversation_id: conversationId } },
      body: { document_id: documentId },
      headers: authHeader(token),
    });
  } catch (error) {
    if (error instanceof ApiRequestError) throw new Error(`HTTP ${error.status}`);
    passOrWrapNetworkError(error);
  }
}

export async function detachDocument(
  token: string | null,
  conversationId: string,
  documentId: number,
): Promise<void> {
  try {
    await api.DELETE("/api/v1/chat/conversations/{conversation_id}/attachments/{document_id}", {
      params: { path: { conversation_id: conversationId, document_id: documentId } },
      headers: authHeader(token),
    });
  } catch (error) {
    if (error instanceof ApiRequestError) throw new Error(`HTTP ${error.status}`);
    passOrWrapNetworkError(error);
  }
}
