import { api, bearer, rethrowOrWrapConnectionError } from "@/lib/api";
import type {
  CreateLLMConfigPayload,
  LLMConfig,
  LLMConfigListResponse,
  ProviderCatalogResponse,
  UpdateLLMConfigPayload,
} from "@/lib/llm/types";

export async function fetchLLMConfigs(
  token: string,
  { includeInactive = false }: { includeInactive?: boolean } = {},
): Promise<LLMConfigListResponse> {
  try {
    const { data } = await api.GET("/api/v1/llm/configs", {
      params: { query: includeInactive ? { include_inactive: true } : undefined },
      headers: bearer(token),
    });
    return data as LLMConfigListResponse;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function createLLMConfig(
  token: string,
  payload: CreateLLMConfigPayload,
): Promise<LLMConfig> {
  try {
    const { data } = await api.POST("/api/v1/llm/configs", {
      body: payload,
      headers: bearer(token),
    });
    return data as LLMConfig;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function updateLLMConfig(
  token: string,
  configId: number,
  payload: UpdateLLMConfigPayload,
): Promise<LLMConfig> {
  if (payload.name === undefined && payload.model === undefined) {
    throw new Error("updateLLMConfig: at least one of name or model must be provided");
  }
  try {
    const { data } = await api.PATCH("/api/v1/llm/configs/{config_id}", {
      params: { path: { config_id: configId } },
      body: payload,
      headers: bearer(token),
    });
    return data as LLMConfig;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function rotateLLMConfigKey(
  token: string,
  configId: number,
  apiKey: string,
): Promise<LLMConfig> {
  try {
    const { data } = await api.PUT("/api/v1/llm/configs/{config_id}/key", {
      params: { path: { config_id: configId } },
      body: { api_key: apiKey },
      headers: bearer(token),
    });
    return data as LLMConfig;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function setLLMConfigActive(
  token: string,
  configId: number,
  isActive: boolean,
): Promise<LLMConfig> {
  try {
    const { data } = await api.PATCH("/api/v1/llm/configs/{config_id}/active", {
      params: { path: { config_id: configId } },
      body: { is_active: isActive },
      headers: bearer(token),
    });
    return data as LLMConfig;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function deleteLLMConfig(token: string, configId: number): Promise<void> {
  try {
    await api.DELETE("/api/v1/llm/configs/{config_id}", {
      params: { path: { config_id: configId } },
      headers: bearer(token),
    });
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}

export async function fetchProviderCatalog(
  token: string,
  options: { signal?: AbortSignal } = {},
): Promise<ProviderCatalogResponse> {
  try {
    const { data } = await api.GET("/api/v1/llm/providers", {
      headers: bearer(token),
      signal: options.signal,
    });
    return data as ProviderCatalogResponse;
  } catch (error) {
    rethrowOrWrapConnectionError(error);
  }
}
