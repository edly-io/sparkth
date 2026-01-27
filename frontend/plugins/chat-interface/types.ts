export interface TextAttachment {
  name: string;
  text: string;
  size: number;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  attachment?: TextAttachment | null;
  streamedContent?: string;
  isTyping?: boolean;
  options?: string[];                 
  pillAttachment?: TextAttachment | null; 
}
