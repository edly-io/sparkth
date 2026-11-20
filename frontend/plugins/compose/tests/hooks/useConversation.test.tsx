import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { ApiRequestError } from "@/lib/api";
import type { ApiMessage } from "@/plugins/compose/src/types";
import { getConversation, getConversationAttachments } from "@/plugins/compose/src/client";
import { useConversation } from "@/plugins/compose/src/hooks/useConversation";
import { addStoredFiles } from "@/plugins/compose/src/storedFiles";

const turn = (id: number, role: ApiMessage["role"], content: string): ApiMessage => ({
  id,
  role,
  content,
  tokens_used: null,
  cost: null,
  created_at: "2026-01-01T00:00:00Z",
  message_type: "text",
  attachment_name: null,
  attachment_size: null,
  is_error: false,
  stopped: false,
});

vi.mock("@/plugins/compose/src/client", () => ({
  getConversation: vi.fn(() =>
    Promise.resolve({
      messages: [
        turn(1, "system", "be concise"),
        turn(2, "user", "hello"),
        turn(3, "tool", "{}"),
        turn(4, "assistant", "hi"),
      ],
    }),
  ),
  getConversationAttachments: vi.fn(() => Promise.resolve([])),
  getLastMessage: vi.fn(),
}));

describe("useConversation — loading history", () => {
  it("shows only user and assistant turns", async () => {
    const { result } = renderHook(() => useConversation("conv-1", "test-token", 7));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.messages.map((m) => [m.role, m.content])).toEqual([
      ["user", "hello"],
      ["assistant", "hi"],
    ]);
  });
});

describe("useConversation — switching chats", () => {
  const renderAt = (initialId: string | null) =>
    renderHook(({ id }: { id: string | null }) => useConversation(id, "test-token", 7), {
      initialProps: { id: initialId },
    });

  it("empties the message box when another chat is opened", async () => {
    const { result, rerender } = renderAt("conv-1");
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setInputMessage("unsent text"));

    rerender({ id: "conv-2" });

    await waitFor(() => expect(result.current.inputMessage).toBe(""));
  });

  it("empties the message box when a new chat is started", async () => {
    const { result, rerender } = renderAt("conv-1");
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setInputMessage("unsent text"));

    rerender({ id: null });

    await waitFor(() => expect(result.current.inputMessage).toBe(""));
  });

  it("keeps the message box when a first send gives the new chat its id", async () => {
    const { result, rerender } = renderAt(null);
    act(() => result.current.setInputMessage("typed while the reply streams"));
    result.current.skipNextLoadRef.current = true;

    rerender({ id: "conv-1" });

    await waitFor(() => expect(result.current.skipNextLoadRef.current).toBe(false));
    expect(result.current.inputMessage).toBe("typed while the reply streams");
  });

  it("drops a chat's load error when a new chat is started", async () => {
    vi.mocked(getConversation).mockRejectedValueOnce(new Error("not found"));
    vi.spyOn(console, "error").mockImplementationOnce(() => {});
    const { result, rerender } = renderAt("not-a-real-id");
    await waitFor(() => expect(result.current.loadError).not.toBeNull());

    rerender({ id: null });

    await waitFor(() => expect(result.current.loadError).toBeNull());
  });

  it("ignores a failure that lands after another chat was opened", async () => {
    let failFirstLoad: (error: unknown) => void = () => {};
    vi.mocked(getConversation).mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          failFirstLoad = reject;
        }),
    );
    const { result, rerender } = renderAt("conv-1");

    rerender({ id: "conv-2" });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () =>
      failFirstLoad(
        new ApiRequestError({ message: "Conversation not found", fieldErrors: {} }, 404),
      ),
    );

    expect(result.current.loadError).toBeNull();
    expect(result.current.messages.map((m) => m.content)).toEqual(["hello", "hi"]);
  });

  it("drops a chat's load error when another chat is opened", async () => {
    vi.mocked(getConversation).mockRejectedValueOnce(new Error("not found"));
    vi.spyOn(console, "error").mockImplementationOnce(() => {});
    const { result, rerender } = renderAt("not-a-real-id");
    await waitFor(() => expect(result.current.loadError).not.toBeNull());

    rerender({ id: "conv-2" });

    await waitFor(() => expect(result.current.loadError).toBeNull());
  });
});

describe("useConversation — a chat that fails to load", () => {
  it.each([404, 403, 422])("reports a chat that does not exist on a %i", async (status) => {
    vi.mocked(getConversation).mockRejectedValueOnce(
      new ApiRequestError({ message: "Conversation not found", fieldErrors: {} }, status),
    );
    vi.spyOn(console, "error").mockImplementationOnce(() => {});

    const { result } = renderHook(() => useConversation("not-a-real-id", "test-token", 7));

    await waitFor(() => expect(result.current.loadError).toBe("notFound"));
    expect(result.current.error).toBeNull();
  });

  it.each([
    ["a server error", new ApiRequestError({ message: "boom", fieldErrors: {} }, 500)],
    ["a network failure", new Error("Network error: Failed to fetch")],
  ])("reports a chat that could not be loaded on %s", async (_, failure) => {
    vi.mocked(getConversation).mockRejectedValueOnce(failure);
    vi.spyOn(console, "error").mockImplementationOnce(() => {});

    const { result } = renderHook(() => useConversation("conv-1", "test-token", 7));

    await waitFor(() => expect(result.current.loadError).toBe("failed"));
    expect(result.current.error).toBeNull();
  });
});

describe("useConversation — attached files line", () => {
  it("lists documents and the computer uploads sent in the conversation", async () => {
    vi.mocked(getConversation).mockResolvedValueOnce({
      messages: [
        {
          ...turn(5, "user", "Week 1"),
          message_type: "attachment",
          attachment_name: "notes.txt",
          attachment_size: 6,
        },
        turn(6, "user", "Summarise this"),
        turn(7, "assistant", "Done"),
      ],
    } as Awaited<ReturnType<typeof getConversation>>);
    vi.mocked(getConversationAttachments).mockResolvedValueOnce([
      { id: 7, name: "drive.pdf", size: 1024, source: "googledrive" },
    ] as Awaited<ReturnType<typeof getConversationAttachments>>);

    const { result } = renderHook(() => useConversation("conv-1", "test-token", 7));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.inputAttachments).toEqual([
      {
        name: "drive.pdf",
        size: 1024,
        text: "[File: drive.pdf]",
        documentId: 7,
        source: "googledrive",
      },
      { name: "notes.txt", size: 6, text: "", uploadId: "message-5", isSent: true },
    ]);
  });

  it("lists the files this browser keeps for the conversation as sent", async () => {
    localStorage.clear();
    addStoredFiles(7, "conv-1", [{ name: "syllabus.txt", size: 12, text: "Week 1: cells" }]);

    const { result } = renderHook(() => useConversation("conv-1", "test-token", 7));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.inputAttachments).toEqual([
      { name: "syllabus.txt", size: 12, text: "", uploadId: "stored-0", isSent: true },
    ]);
  });
});
