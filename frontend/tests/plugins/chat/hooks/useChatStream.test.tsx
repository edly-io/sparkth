import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatStream } from "@/plugins/chat/hooks/useChatStream";
import type { ChatMessage } from "@/plugins/chat/types";

const requestChatCompletionStream = vi.fn();

vi.mock("@/lib/chat", () => ({
  requestChatCompletionStream: (...args: unknown[]) => requestChatCompletionStream(...args),
}));

// Serves the payloads exactly as sparkth/plugins/chat/routes/utils/stream_processor.py writes
// them, so a rename on either side fails this test.
function sseBody(payloads: Record<string, unknown>[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const payload of payloads) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
      }
      controller.close();
    },
  });
}

type AssistantSnapshot = Pick<ChatMessage, "statusPhase" | "streamedContent">;

function runStream(payloads: Record<string, unknown>[]) {
  requestChatCompletionStream.mockResolvedValue({ body: sseBody(payloads) });
  let messages: ChatMessage[] = [];
  const snapshots: AssistantSnapshot[] = [];
  const setMessages = (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    messages = typeof updater === "function" ? updater(messages) : updater;
    // The hook clears the phase once the turn finishes, so the final message never
    // carries it — every intermediate state has to be recorded as it happens.
    const assistant = messages.find((m) => m.role === "assistant");
    if (assistant) {
      snapshots.push({
        statusPhase: assistant.statusPhase,
        streamedContent: assistant.streamedContent,
      });
    }
  };
  const { result } = renderHook(() =>
    useChatStream({
      token: "test-token",
      llmConfigId: 1,
      conversationId: "conv-1",
      setMessages,
      onNewConversation: vi.fn(),
    }),
  );
  return {
    send: () => result.current.handleSend({ message: "hello", attachments: [] }),
    phases: () => snapshots.map((s) => s.statusPhase),
    snapshots: () => snapshots,
  };
}

const DONE = { token: "", done: true, conversation_id: "conv-1" };

describe("useChatStream — status phases", () => {
  beforeEach(() => vi.clearAllMocks());

  it.each(["scanning_attachments", "searching_documents", "skipping_rag", "generating"])(
    "records the %s phase the backend sends",
    async (status) => {
      const stream = runStream([{ status, file_count: 1, done: false }]);
      await act(async () => {
        await stream.send();
      });
      expect(stream.phases()).toContain(status);
    },
  );

  it("clears the phase once the first token arrives", async () => {
    const stream = runStream([
      { status: "searching_documents", file_count: 1, done: false },
      { token: "Here", done: false },
      DONE,
    ]);
    await act(async () => {
      await stream.send();
    });
    const firstToken = stream.snapshots().find((s) => s.streamedContent === "Here");
    expect(firstToken).toBeDefined();
    expect(firstToken?.statusPhase).toBeUndefined();
  });

  it("ignores a status it does not know", async () => {
    const stream = runStream([{ status: "something_new", done: false }, DONE]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.phases().filter(Boolean)).toEqual([]);
  });
});
