import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import type { ApiMessage } from "@/plugins/compose/src/types";
import { getConversation } from "@/plugins/compose/src/client";
import { useConversation } from "@/plugins/compose/src/hooks/useConversation";

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
    const { result } = renderHook(() => useConversation("conv-1", "test-token"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.messages.map((m) => [m.role, m.content])).toEqual([
      ["user", "hello"],
      ["assistant", "hi"],
    ]);
  });
});

describe("useConversation — switching chats", () => {
  const renderAt = (initialId: string | null) =>
    renderHook(({ id }: { id: string | null }) => useConversation(id, "test-token"), {
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
    await waitFor(() => expect(result.current.error).not.toBeNull());

    rerender({ id: null });

    await waitFor(() => expect(result.current.error).toBeNull());
  });
});
