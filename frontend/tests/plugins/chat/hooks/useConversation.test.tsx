import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { useConversation } from "@/plugins/chat/hooks/useConversation";
import type { ApiMessage } from "@/lib/chat/types";

const getConversation = vi.fn();

vi.mock("@/lib/chat", () => ({
  getConversation: (...args: unknown[]) => getConversation(...args),
  getConversationAttachments: vi.fn().mockResolvedValue([]),
  getLastMessage: vi.fn(),
}));

function apiMessage(overrides: Partial<ApiMessage>): ApiMessage {
  return {
    id: 1,
    role: "user",
    content: "",
    message_type: "text",
    attachment_name: null,
    attachment_size: null,
    created_at: "2026-10-13T00:00:00Z",
    rag_sections: null,
    tool_calls: null,
    is_error: false,
    stopped: false,
    ...overrides,
  };
}

const reply = apiMessage({ id: 9, role: "assistant", content: "Here is your course." });

async function loadUserTurn(messages: ApiMessage[]) {
  getConversation.mockResolvedValue({ messages: [...messages, reply] });
  const { result } = renderHook(() => useConversation("conv-1", "token"));
  await waitFor(() => expect(result.current.loading).toBe(false));
  return result.current.messages[0];
}

const uploaded = (overrides: Partial<ApiMessage>) =>
  apiMessage({
    message_type: "attachment",
    attachment_name: "notes.txt",
    attachment_size: 9,
    ...overrides,
  });

describe("useConversation — a reopened turn with a file from the computer", () => {
  it("shows only the typed message, and previews the file from the stored text", async () => {
    const turn = await loadUserTurn([
      uploaded({
        content: "Create a course\n\n---\n\nFILE TEXT",
        attachment_message: "Create a course",
      }),
    ]);

    expect(turn.content).toBe("Create a course");
    expect(turn.attachments).toEqual([
      { name: "notes.txt", size: 9, text: "Create a course\n\n---\n\nFILE TEXT" },
    ]);
  });

  it("shows no text when the file was sent without a message", async () => {
    const turn = await loadUserTurn([uploaded({ content: "FILE TEXT", attachment_message: "" })]);

    expect(turn.content).toBe("");
  });

  it("shows no stand-in text for an older document turn sent without a message", async () => {
    const turn = await loadUserTurn([uploaded({ content: "[Document attachment]" })]);

    expect(turn.content).toBe("");
  });

  it("keeps the typed message from the last of several files", async () => {
    const turn = await loadUserTurn([
      uploaded({ id: 1, content: "AAA", attachment_message: "" }),
      uploaded({ id: 2, content: "Go\n\n---\n\nBBB", attachment_message: "Go" }),
    ]);

    expect(turn.content).toBe("Go");
    expect(turn.attachments).toHaveLength(2);
  });
});
