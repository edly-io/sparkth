import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import {
  attachDocument,
  detachDocument,
  getConversation,
  getConversationAttachments,
  getLastMessage,
  listConversations,
  requestChatCompletionStream,
} from "@/lib/chat";
import type { ChatCompletionRequestBody } from "@/lib/chat/types";

vi.mock("@/lib/auth-tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

const TOKEN = "test-token";

const COMPLETION_BODY: ChatCompletionRequestBody = {
  llm_config_id: 7,
  messages: [{ role: "user", content: "hi" }],
  stream: true,
  temperature: 0.7,
  tools: "*",
  tool_choice: "auto",
  include_system_tools_message: true,
};

function mockFetch(body: unknown, status = 200) {
  const response =
    status === 204
      ? new Response(null, { status })
      : new Response(typeof body === "string" ? body : JSON.stringify(body), { status });
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
}

function sentRequest(spy: ReturnType<typeof mockFetch>): Request {
  return spy.mock.calls[0][0] as Request;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("requestChatCompletionStream", () => {
  it("POSTs the typed payload to /api/v1/chat/completions and returns the raw Response", async () => {
    const spy = mockFetch("data: {}\n\n");

    const res = await requestChatCompletionStream(TOKEN, COMPLETION_BODY);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/completions");
    expect(request.method).toBe("POST");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    const sentBody = await request.clone().json();
    expect(sentBody).toEqual(COMPLETION_BODY);
    expect("similarity_threshold" in sentBody).toBe(false);
    expect(res.status).toBe(200);
    await expect(res.text()).resolves.toBe("data: {}\n\n");
  });

  it("throws ApiRequestError carrying status and detail on non-ok responses", async () => {
    mockFetch({ detail: "No AI Key found for the current user." }, 404);

    const error = await requestChatCompletionStream(TOKEN, COMPLETION_BODY).catch(
      (e: unknown) => e,
    );

    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).status).toBe(404);
    expect((error as ApiRequestError).message).toBe("No AI Key found for the current user.");
  });

  it("wraps a network failure into a readable Error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(requestChatCompletionStream(TOKEN, COMPLETION_BODY)).rejects.toThrow(
      /Network error.*Failed to fetch/,
    );
  });
});

describe("getConversation", () => {
  it("GETs the conversation and returns the parsed body", async () => {
    const conversation = { id: "abc", messages: [] };
    const spy = mockFetch(conversation);
    const controller = new AbortController();

    const result = await getConversation(TOKEN, "abc", controller.signal);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations/abc");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(conversation);
  });

  it("throws with the status code on non-ok response", async () => {
    mockFetch({ detail: "missing" }, 404);

    await expect(getConversation(TOKEN, "missing")).rejects.toThrow(
      "Load conversation failed with status 404",
    );
  });

  it("sends a literal Bearer null header when the token is null (legacy behavior)", async () => {
    const spy = mockFetch({ id: "abc", messages: [] });

    await getConversation(null, "abc");

    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer null");
  });
});

describe("getConversationAttachments", () => {
  it("GETs the attachments list", async () => {
    const files = [{ id: 1, name: "doc.pdf", size: 10 }];
    const spy = mockFetch(files);
    const controller = new AbortController();

    const result = await getConversationAttachments(TOKEN, "abc", controller.signal);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations/abc/attachments");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(files);
  });

  it("returns an empty list on non-ok response (non-fatal)", async () => {
    mockFetch({ detail: "boom" }, 500);

    await expect(getConversationAttachments(TOKEN, "abc")).resolves.toEqual([]);
  });
});

describe("getLastMessage", () => {
  it("GETs the last message", async () => {
    const message = { id: 5, role: "assistant", content: "done" };
    const spy = mockFetch(message);
    const controller = new AbortController();

    const result = await getLastMessage(TOKEN, "abc", controller.signal);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations/abc/last-message");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(message);
  });

  it("returns null on non-ok response (caller keeps polling)", async () => {
    mockFetch({ detail: "boom" }, 500);

    await expect(getLastMessage(TOKEN, "abc")).resolves.toBeNull();
  });
});

describe("listConversations", () => {
  it("GETs the conversations list and unwraps the envelope", async () => {
    const conversations = [{ id: "abc", title: "T", message_count: 1 }];
    const spy = mockFetch({ conversations });
    const controller = new AbortController();

    const result = await listConversations(TOKEN, controller.signal);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(conversations);
  });

  it("returns an empty list when the envelope is missing", async () => {
    mockFetch({});

    await expect(listConversations(TOKEN)).resolves.toEqual([]);
  });

  it("throws with the status code on non-ok response", async () => {
    mockFetch({ detail: "boom" }, 500);

    await expect(listConversations(TOKEN)).rejects.toThrow(
      "Failed to load conversations: HTTP 500",
    );
  });
});

describe("attachDocument", () => {
  it("POSTs the document id", async () => {
    const spy = mockFetch({ id: 1, conversation_id: 2, document_id: 42, attached_at: "now" });

    await attachDocument(TOKEN, "abc", 42);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations/abc/attachments");
    expect(request.method).toBe("POST");
    expect(request.headers.get("authorization")).toBe("Bearer test-token");
    await expect(request.clone().json()).resolves.toEqual({ document_id: 42 });
  });

  it("throws on non-ok response", async () => {
    mockFetch({ detail: "boom" }, 500);

    await expect(attachDocument(TOKEN, "abc", 42)).rejects.toThrow("HTTP 500");
  });
});

describe("detachDocument", () => {
  it("DELETEs the attachment", async () => {
    const spy = mockFetch(null, 204);

    await detachDocument(TOKEN, "abc", 42);

    const request = sentRequest(spy);
    expect(new URL(request.url).pathname).toBe("/api/v1/chat/conversations/abc/attachments/42");
    expect(request.method).toBe("DELETE");
  });

  it("throws on non-ok response", async () => {
    mockFetch({ detail: "missing" }, 404);

    await expect(detachDocument(TOKEN, "abc", 42)).rejects.toThrow("HTTP 404");
  });
});

describe("network error handling", () => {
  it("wraps a network failure into a readable Error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(getConversation(TOKEN, "abc")).rejects.toThrow(/Network error.*Failed to fetch/);
  });

  it("lets AbortError pass through unchanged", async () => {
    const abortError = new DOMException("aborted", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(abortError);

    await expect(listConversations(TOKEN)).rejects.toBe(abortError);
  });
});
