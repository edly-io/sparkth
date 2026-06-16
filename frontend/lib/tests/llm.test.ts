import { describe, it, expect, vi, beforeEach } from "vitest";

import { fetchProviderCatalog } from "@/lib/llm";

describe("fetchProviderCatalog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the provider catalog and forwards the abort signal", async () => {
    const catalog = { providers: [], default_provider: "openai", default_model: "gpt-4o" };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(catalog), { status: 200 }));
    const controller = new AbortController();

    const result = await fetchProviderCatalog("test-token", { signal: controller.signal });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/llm/providers",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
        signal: controller.signal,
      }),
    );
    expect(result).toEqual(catalog);
  });

  it("re-throws AbortError unwrapped so callers can ignore aborted requests", async () => {
    const abortError = new DOMException("The operation was aborted.", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abortError);

    await expect(fetchProviderCatalog("test-token")).rejects.toBe(abortError);
  });
});
