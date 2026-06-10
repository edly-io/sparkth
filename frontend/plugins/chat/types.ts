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
  statusText?: string;
  ragSections?: { type: string; name: string; source?: string; state: "scanning" | "confirmed" }[];
  toolCalls?: { name: string; status: "running" | "done" }[];
}
