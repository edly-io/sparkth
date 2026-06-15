import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import {
  createLLMConfig,
  deleteLLMConfig,
  fetchLLMConfigs,
  fetchProviderCatalog,
  rotateLLMConfigKey,
  setLLMConfigActive,
  updateLLMConfig,
} from "@/lib/llm";

import { mockFetch, sentRequest } from "./test-utils";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

const CONFIG = {
  id: 7,
  name: "Work key",
  provider: "anthropic",
  model: "claude-sonnet-4-20250514",
  masked_key: "sk-...abcd",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_used_at: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("fetchLLMConfigs", () => {
  it("GETs /api/v1/llm/configs with the bearer token and no query by default", async () => {
    const payload = { configs: [CONFIG], total: 1 };
    const spy = mockFetch(payload);

    const result = await fetchLLMConfigs("test-token");

    const request = sentRequest(spy);
    const url = new URL(request.url);
    expect(url.pathname).toBe("/api/v1/llm/configs");
    expect(url.search).toBe("");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(payload);
  });

  it("serializes include_inactive=true when requested", async () => {
    const spy = mockFetch({ configs: [], total: 0 });

    await fetchLLMConfigs("test-token", { includeInactive: true });

    expect(new URL(sentRequest(spy).url).search).toBe("?include_inactive=true");
  });
});

describe("createLLMConfig", () => {
  it("POSTs the payload and returns the created config", async () => {
    const spy = mockFetch(CONFIG, 201);
    const payload = {
      name: "Work key",
      provider: "anthropic",
      model: "claude-sonnet-4-20250514",
      api_key: "sk-ant-xxx",
    };

    const result = await createLLMConfig("test-token", payload);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/configs");
    expect(request.method).toBe("POST");
    await expect(request.clone().json()).resolves.toEqual(payload);
    expect(result).toEqual(CONFIG);
  });
});

describe("updateLLMConfig", () => {
  it("PATCHes the config by id", async () => {
    const spy = mockFetch(CONFIG);

    const result = await updateLLMConfig("test-token", 7, { name: "Renamed" });

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/configs/7");
    expect(request.method).toBe("PATCH");
    await expect(request.clone().json()).resolves.toEqual({ name: "Renamed" });
    expect(result).toEqual(CONFIG);
  });

  it("rejects an empty patch client-side", async () => {
    const spy = vi.spyOn(globalThis, "fetch");

    await expect(updateLLMConfig("test-token", 7, {})).rejects.toThrow(
      "updateLLMConfig: at least one of name or model must be provided",
    );
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("rotateLLMConfigKey", () => {
  it("PUTs the new api key", async () => {
    const spy = mockFetch(CONFIG);

    await rotateLLMConfigKey("test-token", 7, "sk-new");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/configs/7/key");
    expect(request.method).toBe("PUT");
    await expect(request.clone().json()).resolves.toEqual({ api_key: "sk-new" });
  });
});

describe("setLLMConfigActive", () => {
  it("PATCHes the active flag", async () => {
    const spy = mockFetch(CONFIG);

    await setLLMConfigActive("test-token", 7, false);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/configs/7/active");
    expect(request.method).toBe("PATCH");
    await expect(request.clone().json()).resolves.toEqual({ is_active: false });
  });
});

describe("deleteLLMConfig", () => {
  it("DELETEs the config and resolves on 204", async () => {
    const spy = mockFetch(null, 204);

    await expect(deleteLLMConfig("test-token", 7)).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/configs/7");
    expect(request.method).toBe("DELETE");
  });
});

describe("fetchProviderCatalog", () => {
  it("GETs the provider catalog with the bearer token and forwards the abort signal", async () => {
    const catalog = { providers: [], default_provider: "openai", default_model: "gpt-4o" };
    const spy = mockFetch(catalog);
    const controller = new AbortController();

    const result = await fetchProviderCatalog("test-token", { signal: controller.signal });

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/llm/providers");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(request.signal.aborted).toBe(false);
    controller.abort();
    expect(request.signal.aborted).toBe(true);
    expect(result).toEqual(catalog);
  });

  it("re-throws AbortError unwrapped so callers can ignore aborted requests", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abortError);

    await expect(fetchProviderCatalog("test-token")).rejects.toBe(abortError);
  });

  it("maps error envelopes to ApiRequestError with status", async () => {
    mockFetch({ detail: "boom" }, 500);

    const error = await fetchProviderCatalog("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("boom");
    expect((error as ApiRequestError).status).toBe(500);
  });

  it("wraps network failures as connection errors", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await fetchProviderCatalog("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).message).toBe("Unable to connect to server: Failed to fetch");
  });
});
