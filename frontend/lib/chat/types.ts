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
  // `unknown[]` for multipart content (e.g. image/text blocks): callers must
  // narrow before use until we share a typed content-parts schema with the backend.
  content: string | unknown[];
  attachment?: { name: string; size: number };
}

export interface ChatCompletionRequestBody {
  llm_config_id?: number;
  model_override?: string;
  messages: OutgoingChatMessage[];
  stream: boolean;
  tools: string;
  tool_choice: string;
  include_system_tools_message: boolean;
  similarity_threshold: number;
  conversation_id?: string;
  document_ids?: number[];
}
