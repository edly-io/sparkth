import type { Schema } from "@/lib/api";

// ApiMessage and ApiConversation deliberately narrow the generated
// MessageResponse/ConversationDetailResponse: role, message_type,
// rag_sections and tool_calls are JSON dicts on the wire, and their concrete
// shapes are client-side knowledge (same category as the SSE event payloads).
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

export type ConversationSummary = Schema<"ConversationResponse">;
export type PersistedAttachment = Schema<"AttachedDocumentResponse">;
export type ChatCompletionRequestBody = Schema<"ChatCompletionRequest">;
