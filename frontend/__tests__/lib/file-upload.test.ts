import { describe, it, expect, vi, beforeEach } from "vitest";

import { uploadFile } from "@/lib/file-upload";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

function mockFetch(body: unknown, status = 200) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(body), { status }));
}

function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}

function makeFormData(): FormData {
  const formData = new FormData();
  formData.append("file", new File(["hello"], "notes.txt", { type: "text/plain" }));
  return formData;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("uploadFile", () => {
  it("POSTs multipart form data to the parser endpoint with the bearer token", async () => {
    const parsed = { filename: "notes.txt", length: 5, text: "hello" };
    const spy = mockFetch(parsed);

    const result = await uploadFile(makeFormData(), "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/parser/upload");
    expect(request.method).toBe("POST");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(request.headers.get("content-type")).toMatch(/^multipart\/form-data; boundary=/);
    expect(result).toEqual(parsed);
  });

  it("sends no authorization header when no token is given and storage is empty", async () => {
    const spy = mockFetch({ filename: "n", length: 0, text: "" });

    await uploadFile(makeFormData());

    expect(sentRequest(spy).headers.get("authorization")).toBeNull();
  });

  it("throws a plain Error carrying the bare backend detail", async () => {
    mockFetch({ detail: "Unsupported file type" }, 415);

    const error = await uploadFile(makeFormData(), "test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(Error);
    expect(error).not.toHaveProperty("fieldErrors");
    expect((error as Error).message).toBe("Unsupported file type");
  });

  it("lets network failures propagate untouched", async () => {
    const boom = new TypeError("Failed to fetch");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(boom);

    await expect(uploadFile(makeFormData(), "test-token")).rejects.toBe(boom);
  });
});
