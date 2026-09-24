// What is missing before a course can be composed: no AI key at all, or one that exists but was
// never selected in the plugin's configuration.
export type AiKeyProblem = "no-key" | "not-selected";

export interface TextAttachment {
  name: string;
  text: string;
  size: number;
  base64Data?: string;
  mediaType?: string;
  driveFileDbId?: number; // Google Drive file DB ID used only by the picker UI.
  documentId?: number; // Core Document ID used by chat/RAG.
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
  options?: string[];
  pillAttachment?: TextAttachment | null;
  statusPhase?: StreamStatusPhase;
  ragSections?: { type: string; name: string; source?: string; state: "scanning" | "confirmed" }[];
  toolCalls?: { name: string; status: "running" | "done" }[];
  stopped?: boolean;
}
