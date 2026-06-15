import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  browseDrive,
  createFolder,
  deleteFile,
  disconnectGoogle,
  downloadFile,
  getAuthorizationUrl,
  getConnectionStatus,
  getFolder,
  getFolderRagStatus,
  listFiles,
  listFolders,
  refreshFolder,
  removeFolder,
  renameFile,
  syncFolder,
  uploadFile,
} from "@/lib/drive";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

function mockFetch(body: unknown, status = 200) {
  const response =
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), { status });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("oauth", () => {
  it("getConnectionStatus GETs the status endpoint with the bearer token", async () => {
    const status = { connected: true, email: "u@example.com", expires_at: "2026-01-01" };
    const spy = mockFetch(status);

    const result = await getConnectionStatus("test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/oauth/status");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(status);
  });

  it("getConnectionStatus throws a plain Error with the backend detail", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch({ detail: "plugin disabled" }, 403);

    const error = await getConnectionStatus("test-token").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(Error);
    expect(error).not.toHaveProperty("fieldErrors");
    expect((error as Error).message).toBe("Failed to get connection status: plugin disabled");
  });

  it("getConnectionStatus lets network failures propagate untouched", async () => {
    const boom = new TypeError("Failed to fetch");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(boom);

    await expect(getConnectionStatus("test-token")).rejects.toBe(boom);
  });

  it("getAuthorizationUrl unwraps the url", async () => {
    const spy = mockFetch({ url: "https://accounts.google.com/o/x" });

    const result = await getAuthorizationUrl("test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/google-drive/oauth/authorize");
    expect(result).toBe("https://accounts.google.com/o/x");
  });

  it("disconnectGoogle DELETEs the disconnect endpoint", async () => {
    const spy = mockFetch({ ok: true });

    await expect(disconnectGoogle("test-token")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/oauth/disconnect");
    expect(request.method).toBe("DELETE");
  });
});

describe("folders", () => {
  it("listFolders GETs with default pagination", async () => {
    const page = { items: [], total: 0, skip: 0, limit: 20 };
    const spy = mockFetch(page);

    const result = await listFolders("test-token");

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/google-drive/folders");
    expect(url.searchParams.get("skip")).toBe("0");
    expect(url.searchParams.get("limit")).toBe("20");
    expect(result).toEqual(page);
  });

  it("listFolders forwards explicit pagination", async () => {
    const spy = mockFetch({ items: [], total: 0, skip: 40, limit: 10 });

    await listFolders("test-token", 40, 10);

    const url = new URL(sentRequest(spy).url);
    expect(url.searchParams.get("skip")).toBe("40");
    expect(url.searchParams.get("limit")).toBe("10");
  });

  it("syncFolder POSTs the drive folder id", async () => {
    const folder = {
      id: 1,
      drive_folder_id: "abc",
      name: "F",
      file_count: 0,
      sync_status: "queued",
    };
    const spy = mockFetch(folder);

    const result = await syncFolder("abc", "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders/sync");
    expect(request.method).toBe("POST");
    await expect(request.clone().json()).resolves.toEqual({ drive_folder_id: "abc" });
    expect(result).toEqual(folder);
  });

  it("createFolder POSTs name and parent id", async () => {
    const folder = {
      id: 2,
      drive_folder_id: "xyz",
      name: "New",
      file_count: 0,
      sync_status: "synced",
    };
    const spy = mockFetch(folder);

    const result = await createFolder("New", "parent-1", "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders");
    expect(request.method).toBe("POST");
    await expect(request.clone().json()).resolves.toEqual({ name: "New", parent_id: "parent-1" });
    expect(result).toEqual(folder);
  });

  it("getFolder GETs the folder by id", async () => {
    const folder = {
      id: 7,
      drive_folder_id: "abc",
      name: "F",
      file_count: 1,
      sync_status: "synced",
      files: [],
    };
    const spy = mockFetch(folder);

    const result = await getFolder(7, "test-token");

    expect(new URL(sentRequest(spy).url).pathname).toBe("/api/v1/google-drive/folders/7");
    expect(result).toEqual(folder);
  });

  it("removeFolder DELETEs the folder and resolves on 204", async () => {
    const spy = mockFetch(null, 204);

    await expect(removeFolder(7, "test-token")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders/7");
    expect(request.method).toBe("DELETE");
  });

  it("refreshFolder POSTs the refresh endpoint", async () => {
    const status = { folder_id: 7, sync_status: "queued" };
    const spy = mockFetch(status);

    const result = await refreshFolder(7, "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders/7/refresh");
    expect(request.method).toBe("POST");
    expect(result).toEqual(status);
  });
});

describe("files", () => {
  it("listFiles GETs folder files with pagination", async () => {
    const page = { items: [], total: 0, skip: 0, limit: 20 };
    const spy = mockFetch(page);

    const result = await listFiles(7, "test-token");

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/google-drive/folders/7/files");
    expect(url.searchParams.get("skip")).toBe("0");
    expect(url.searchParams.get("limit")).toBe("20");
    expect(result).toEqual(page);
  });

  it("uploadFile POSTs multipart form data with the file", async () => {
    const uploaded = { id: 9, drive_file_id: "f9", name: "doc.pdf" };
    const spy = mockFetch(uploaded, 201);
    const file = new File(["hello"], "doc.pdf", { type: "application/pdf" });

    const result = await uploadFile(7, file, "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders/7/files");
    expect(request.method).toBe("POST");
    // Reading the body back hangs under jsdom (jsdom File vs undici stream),
    // so pin the multipart contract via the boundary header instead.
    expect(request.headers.get("content-type")).toMatch(/^multipart\/form-data; boundary=/);
    expect(result).toEqual(uploaded);
  });

  it("downloadFile resolves to a Blob with the body bytes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("binary-bytes", { status: 200 }));

    const blob = await downloadFile(9, "test-token");

    expect(blob).toBeInstanceOf(Blob);
    await expect(blob.text()).resolves.toBe("binary-bytes");
  });

  it("renameFile PATCHes the new name", async () => {
    const renamed = { id: 9, drive_file_id: "f9", name: "new.pdf" };
    const spy = mockFetch(renamed);

    const result = await renameFile(9, "new.pdf", "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/files/9");
    expect(request.method).toBe("PATCH");
    await expect(request.clone().json()).resolves.toEqual({ name: "new.pdf" });
    expect(result).toEqual(renamed);
  });

  it("deleteFile DELETEs the file", async () => {
    const spy = mockFetch(null, 204);

    await expect(deleteFile(9, "test-token")).resolves.toBeUndefined();

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/files/9");
    expect(request.method).toBe("DELETE");
  });
});

describe("browseDrive", () => {
  it("GETs the browse endpoint without query when no parent is given", async () => {
    const listing = { items: [], next_page_token: null };
    const spy = mockFetch(listing);

    const result = await browseDrive(undefined, "test-token");

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/google-drive/browse");
    expect(url.search).toBe("");
    expect(result).toEqual(listing);
  });

  it("passes folder_id when a parent is given", async () => {
    const spy = mockFetch({ items: [], next_page_token: null });

    await browseDrive("abc", "test-token");

    expect(new URL(sentRequest(spy).url).searchParams.get("folder_id")).toBe("abc");
  });
});

describe("getFolderRagStatus", () => {
  it("calls the correct endpoint and returns parsed response", async () => {
    const mockResponse = {
      folder_id: 42,
      files: [
        { file_id: 1, name: "doc.pdf", rag_status: "ready" },
        { file_id: 2, name: "notes.txt", rag_status: "processing" },
      ],
    };
    const spy = mockFetch(mockResponse);

    const result = await getFolderRagStatus(42, "test-token");

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/google-drive/folders/42/rag-status");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(mockResponse);
  });

  it("throws on non-ok response", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch({ detail: "Not found" }, 404);

    await expect(getFolderRagStatus(99, "test-token")).rejects.toThrow("Failed to get RAG status");
  });
});
