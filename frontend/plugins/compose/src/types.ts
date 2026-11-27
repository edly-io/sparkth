import type { paths, Schema } from "@/lib/api";

/** A stored chat message, as the chat API returns it. */
export type ApiMessage = Schema<"MessageResponse">;
/** A conversation with its messages, as the chat API returns it. */
export type ApiConversation = Schema<"ConversationDetailResponse">;
/** A conversation's history-list entry, without its messages. */
export type ConversationSummary = Schema<"ConversationResponse">;
/** A plan as the author sees it: its tasks, the step it is at (0 before the first starts) and whether that step has run. */
export type PlanSnapshot = Schema<"PlanSnapshot">;
/** A tool call a reply made: the tool's name and where the call stands. */
export type ToolCall = Schema<"PersistedToolCall">;
/** A document attached to a conversation. */
export type PersistedAttachment = Schema<"AttachedDocumentResponse">;
/** A file uploaded from the computer that a conversation still has, without its text. */
export type UploadedFile = Schema<"UploadedFileResponse">;
/** The request body of the chat completions endpoint. */
export type ChatCompletionRequestBody = Schema<"ChatCompletionRequest">;

// What is missing before a course can be composed: no AI key at all, or one that exists but was
// never selected in the plugin's configuration.
export type AiKeyProblem = "no-key" | "not-selected";

/** Why a chat failed to load: it does not exist for this user, or it could not be fetched. */
export type ConversationLoadError = "notFound" | "failed";

export interface TextAttachment {
  name: string;
  text?: string; // The text read from an upload waiting to be sent; no other file holds it here.
  size: number;
  documentId?: number; // Core Document ID used by chat/RAG.
  source?: string; // The id of the attachment source a document came from, which gives its icon.
  uploadId?: string; // Identifies a file uploaded from the computer, which has no document ID.
  isSent?: boolean; // An upload already sent, which the server keeps for the conversation.
  isStoredInMessage?: boolean; // An older upload whose text is inside a stored message, so it can't be removed.
  isUploading?: boolean; // An upload still on its way to the server, with no text yet.
}

/** Whether an attachment is a file from the computer that will go with the next message. */
export function isUnsentUpload(attachment: TextAttachment): boolean {
  return attachment.documentId === undefined && !attachment.isSent;
}

export type ChatRole = "user" | "assistant";

/** A status event of a streamed reply, as the chat API sends it. */
export type StreamStatusEvent =
  paths["/api/v1/compose/completions"]["post"]["responses"][200]["content"]["text/event-stream"];

/** The statuses shown as a line of text while the reply is on its way. */
export const STREAM_STATUS_PHASES = [
  "generating",
] as const satisfies readonly StreamStatusEvent["status"][];

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
  stepLabel?: string;
  plan?: PlanSnapshot;
  ragSections?: {
    type: string;
    name: string;
    source?: string | null;
    state: "scanning" | "confirmed";
  }[];
  toolCalls?: ToolCall[];
  stopped?: boolean;
}
