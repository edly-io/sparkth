import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import type { ApiMessage } from "@/lib/compose";
import { useConversation } from "@/plugins/compose/hooks/useConversation";

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

vi.mock("@/lib/compose", () => ({
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
