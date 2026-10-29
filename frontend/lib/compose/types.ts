import type { Schema } from "@/lib/api";

export type ApiMessage = Schema<"MessageResponse">;
export type ApiConversation = Schema<"ConversationDetailResponse">;
export type ConversationSummary = Schema<"ConversationResponse">;
export type PersistedAttachment = Schema<"AttachedDocumentResponse">;
export type ChatCompletionRequestBody = Schema<"ChatCompletionRequest">;
