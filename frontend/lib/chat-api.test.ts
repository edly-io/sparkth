import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  attachDriveFile,
  detachDriveFile,
  getConversation,
  getConversationAttachments,
  getLastMessage,
  listConversations,
  requestChatCompletionStream,
} from "./chat-api";

const TOKEN = "test-token";

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

describe("requestChatCompletionStream", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs the payload to /api/v1/chat/completions with auth headers", async () => {
    const fetchSpy = mockFetch(new Response("", { status: 200 }));
    const body = {
      llm_config_id: 7,
      messages: [{ role: "user", content: "hi" }],
      stream: true,
      tools: "*",
      tool_choice: "auto",
      include_system_tools_message: true,
      similarity_threshold: 0.45,
    };

    await requestChatCompletionStream(TOKEN, body);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/completions",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-token",
        }),
        body: JSON.stringify(body),
      }),
    );
  });

  it("returns the raw Response without throwing on non-ok status", async () => {
    mockFetch(new Response(JSON.stringify({ detail: "boom" }), { status: 500 }));

    const res = await requestChatCompletionStream(TOKEN, {
      llm_config_id: undefined,
      messages: [],
      stream: true,
      tools: "*",
      tool_choice: "auto",
      include_system_tools_message: true,
      similarity_threshold: 0.45,
    });

    expect(res.status).toBe(500);
  });
});

describe("getConversation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the conversation and returns the parsed body", async () => {
    const conversation = { id: "abc", messages: [] };
    const fetchSpy = mockFetch(new Response(JSON.stringify(conversation), { status: 200 }));
    const controller = new AbortController();

    const result = await getConversation(TOKEN, "abc", controller.signal);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/abc",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
        signal: controller.signal,
      }),
    );
    expect(result).toEqual(conversation);
  });

  it("throws with the status code on non-ok response", async () => {
    mockFetch(new Response("", { status: 404 }));

    await expect(getConversation(TOKEN, "missing")).rejects.toThrow(
      "Load conversation failed with status 404",
    );
  });
});

describe("getConversationAttachments", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the attachments list", async () => {
    const files = [{ id: 1, name: "doc.pdf", size: 10 }];
    const fetchSpy = mockFetch(new Response(JSON.stringify(files), { status: 200 }));

    const result = await getConversationAttachments(TOKEN, "abc");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/abc/attachments",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(result).toEqual(files);
  });

  it("returns an empty list on non-ok response (non-fatal)", async () => {
    mockFetch(new Response("", { status: 500 }));

    await expect(getConversationAttachments(TOKEN, "abc")).resolves.toEqual([]);
  });
});

describe("getLastMessage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the last message", async () => {
    const message = { id: 5, role: "assistant", content: "done" };
    const fetchSpy = mockFetch(new Response(JSON.stringify(message), { status: 200 }));

    const result = await getLastMessage(TOKEN, "abc");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/abc/last-message",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(result).toEqual(message);
  });

  it("returns null on non-ok response (caller keeps polling)", async () => {
    mockFetch(new Response("", { status: 500 }));

    await expect(getLastMessage(TOKEN, "abc")).resolves.toBeNull();
  });
});

describe("listConversations", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the conversations list and unwraps the envelope", async () => {
    const conversations = [{ id: "abc", title: "T", message_count: 1 }];
    const fetchSpy = mockFetch(new Response(JSON.stringify({ conversations }), { status: 200 }));

    const result = await listConversations(TOKEN);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
    expect(result).toEqual(conversations);
  });

  it("returns an empty list when the envelope is missing", async () => {
    mockFetch(new Response(JSON.stringify({}), { status: 200 }));

    await expect(listConversations(TOKEN)).resolves.toEqual([]);
  });

  it("throws with the status code on non-ok response", async () => {
    mockFetch(new Response("", { status: 500 }));

    await expect(listConversations(TOKEN)).rejects.toThrow(
      "Failed to load conversations: HTTP 500",
    );
  });
});

describe("attachDriveFile", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs the drive file id", async () => {
    const fetchSpy = mockFetch(new Response("", { status: 200 }));

    await attachDriveFile(TOKEN, "abc", 42);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/abc/attachments",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-token",
        }),
        body: JSON.stringify({ drive_file_id: 42 }),
      }),
    );
  });

  it("throws on non-ok response", async () => {
    mockFetch(new Response("", { status: 500 }));

    await expect(attachDriveFile(TOKEN, "abc", 42)).rejects.toThrow("HTTP 500");
  });
});

describe("detachDriveFile", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("DELETEs the attachment", async () => {
    const fetchSpy = mockFetch(new Response("", { status: 200 }));

    await detachDriveFile(TOKEN, "abc", 42);

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/v1/chat/conversations/abc/attachments/42",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("throws on non-ok response", async () => {
    mockFetch(new Response("", { status: 404 }));

    await expect(detachDriveFile(TOKEN, "abc", 42)).rejects.toThrow("HTTP 404");
  });
});
