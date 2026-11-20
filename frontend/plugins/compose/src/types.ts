import type { Schema } from "@/lib/api";

/** A stored chat message, as the chat API returns it. */
export type ApiMessage = Schema<"MessageResponse">;
/** A conversation with its messages, as the chat API returns it. */
export type ApiConversation = Schema<"ConversationDetailResponse">;
/** A conversation's history-list entry, without its messages. */
export type ConversationSummary = Schema<"ConversationResponse">;
/** A document attached to a conversation. */
export type PersistedAttachment = Schema<"AttachedDocumentResponse">;
/** The request body of the chat completions endpoint. */
export type ChatCompletionRequestBody = Schema<"ChatCompletionRequest">;

// What is missing before a course can be composed: no AI key at all, or one that exists but was
// never selected in the plugin's configuration.
export type AiKeyProblem = "no-key" | "not-selected";

/** Why a chat failed to load: it does not exist for this user, or it could not be fetched. */
export type ConversationLoadError = "notFound" | "failed";

export interface TextAttachment {
  name: string;
  text: string;
  size: number;
  base64Data?: string;
  mediaType?: string;
  documentId?: number; // Core Document ID used by chat/RAG.
  source?: string; // The id of the attachment source a document came from, which gives its icon.
  uploadId?: string; // Identifies a file uploaded from the computer, which has no document ID.
  isSent?: boolean; // An upload already sent, whose text is now part of the conversation.
  isUploading?: boolean; // An upload still on its way to the server, with no text yet.
}

/** Whether an attachment is a file from the computer that will go with the next message. */
export function isUnsentUpload(attachment: TextAttachment): boolean {
  return attachment.documentId === undefined && !attachment.isSent;
}

export type ChatRole = "user" | "assistant";

// The status names the chat stream sends; stored verbatim so a rename cannot go unnoticed.
export const STREAM_STATUS_PHASES = [
  "scanning_attachments",
  "searching_documents",
  "skipping_rag",
  "generating",
] as const;

export type StreamStatusPhase = (typeof STREAM_STATUS_PHASES)[number];

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  attachments?: TextAttachment[];
  streamedContent?: string;
  isTyping?: boolean;
  isError?: boolean;
  isPending?: boolean;
  statusPhase?: StreamStatusPhase;
  ragSections?: {
    type: string;
    name: string;
    source?: string | null;
    state: "scanning" | "confirmed";
  }[];
  toolCalls?: { name: string; status: "running" | "done" }[];
  stopped?: boolean;
}
