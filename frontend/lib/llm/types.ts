import type { Schema } from "@/lib/api";

export type LLMConfig = Schema<"LLMConfigResponse">;
export type LLMConfigListResponse = Schema<"LLMConfigListResponse">;
export type ProviderInfo = Schema<"ProviderInfo">;
export type ProviderCatalogResponse = Schema<"ProviderCatalogResponse">;
export type CreateLLMConfigPayload = Schema<"LLMConfigCreate">;
export type UpdateLLMConfigPayload = Schema<"LLMConfigUpdate">;
