export interface LLMConfig {
  id: number;
  name: string;
  provider: string;
  model: string;
  masked_key: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface LLMConfigListResponse {
  configs: LLMConfig[];
  total: number;
}

export interface ProviderInfo {
  id: string;
  label: string;
  models: string[];
}

export interface ProviderCatalogResponse {
  providers: ProviderInfo[];
  default_provider: string | null;
  default_model: string | null;
}

export interface CreateLLMConfigPayload {
  name: string;
  provider: string;
  model: string;
  api_key: string;
}

export interface UpdateLLMConfigPayload {
  name?: string;
  model?: string;
}
