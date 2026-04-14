import { describe, it, expect, vi, beforeEach } from "vitest";

// getFolderRagStatus does not exist yet — this test must fail
import { getFolderRagStatus } from "./drive";

describe("getFolderRagStatus", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the correct endpoint and returns parsed response", async () => {
    const mockResponse = {
      folder_id: 42,
      files: [
        { file_id: 1, name: "doc.pdf", rag_status: "ready" },
        { file_id: 2, name: "notes.txt", rag_status: "processing" },
      ],
    };

    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }));

    const result = await getFolderRagStatus(42, "test-token");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/googledrive/folders/42/rag-status",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      }),
    );
    expect(result).toEqual(mockResponse);
  });

  it("throws on non-ok response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    );

    await expect(getFolderRagStatus(99, "test-token")).rejects.toThrow("Failed to get RAG status");
  });
});
