import { ApiRequestError, type ApiError, formatApiError } from "./api";

const API_BASE = "/api/v1/llm";

function jsonHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };
}

function readHeaders(token: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  };
}

async function llmFetch(url: string, init: RequestInit, errorAction: string): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    throw new ApiRequestError({
      message: `Unable to connect to server: ${message}`,
      fieldErrors: {},
    });
  }
  if (!response.ok) {
    try {
      const apiError: ApiError = await response.json();
      throw new ApiRequestError(formatApiError(apiError));
    } catch (e) {
      if (e instanceof ApiRequestError) throw e;
      throw new ApiRequestError({
        message: `${errorAction} (HTTP ${response.status}). Please try again.`,
        fieldErrors: {},
      });
    }
  }
  return response;
}

// ─── Types ───────────────────────────────────────────────────────────────────

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

// ─── API Functions ───────────────────────────────────────────────────────────

export async function fetchLLMConfigs(
  token: string,
  { includeInactive = false }: { includeInactive?: boolean } = {},
): Promise<LLMConfigListResponse> {
  const url = includeInactive ? `${API_BASE}/configs?include_inactive=true` : `${API_BASE}/configs`;
  return (
    await llmFetch(url, { headers: readHeaders(token) }, "Failed to fetch LLM configs")
  ).json();
}

export async function createLLMConfig(
  token: string,
  payload: CreateLLMConfigPayload,
): Promise<LLMConfig> {
  return (
    await llmFetch(
      `${API_BASE}/configs`,
      { method: "POST", headers: jsonHeaders(token), body: JSON.stringify(payload) },
      "Failed to create LLM config",
    )
  ).json();
}

export async function updateLLMConfig(
  token: string,
  configId: number,
  payload: UpdateLLMConfigPayload,
): Promise<LLMConfig> {
  if (payload.name === undefined && payload.model === undefined) {
    throw new Error("updateLLMConfig: at least one of name or model must be provided");
  }
  return (
    await llmFetch(
      `${API_BASE}/configs/${configId}`,
      { method: "PATCH", headers: jsonHeaders(token), body: JSON.stringify(payload) },
      "Failed to update LLM config",
    )
  ).json();
}

export async function rotateLLMConfigKey(
  token: string,
  configId: number,
  apiKey: string,
): Promise<LLMConfig> {
  return (
    await llmFetch(
      `${API_BASE}/configs/${configId}/key`,
      { method: "PUT", headers: jsonHeaders(token), body: JSON.stringify({ api_key: apiKey }) },
      "Failed to rotate API key",
    )
  ).json();
}

export async function setLLMConfigActive(
  token: string,
  configId: number,
  isActive: boolean,
): Promise<LLMConfig> {
  return (
    await llmFetch(
      `${API_BASE}/configs/${configId}/active`,
      {
        method: "PATCH",
        headers: jsonHeaders(token),
        body: JSON.stringify({ is_active: isActive }),
      },
      "Failed to update config status",
    )
  ).json();
}

export async function deleteLLMConfig(token: string, configId: number): Promise<void> {
  await llmFetch(
    `${API_BASE}/configs/${configId}`,
    { method: "DELETE", headers: readHeaders(token) },
    "Failed to delete LLM config",
  );
}

export async function fetchProviderCatalog(token: string): Promise<ProviderCatalogResponse> {
  return (
    await llmFetch(
      `${API_BASE}/providers`,
      { headers: readHeaders(token) },
      "Failed to fetch providers",
    )
  ).json();
}
