export interface TextAttachment {
  name: string;
  text: string;
  size: number;
  base64Data?: string;
  mediaType?: string;
  driveFileDbId?: number; // Database ID of the DriveFile — triggers RAG retrieval on send
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  attachment?: TextAttachment | null;
  streamedContent?: string;
  isTyping?: boolean;
  isError?: boolean;
  options?: string[];
  pillAttachment?: TextAttachment | null;
  statusText?: string;
  ragSections?: { type: string; name: string; state: "scanning" | "confirmed" }[];
}
