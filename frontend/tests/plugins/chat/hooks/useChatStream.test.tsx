import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatStream } from "@/plugins/chat/hooks/useChatStream";
import type { ChatMessage } from "@/plugins/chat/types";

const requestChatCompletionStream = vi.fn();
const stopChatTurn = vi.fn().mockResolvedValue(undefined);

vi.mock("@/lib/chat", () => ({
  requestChatCompletionStream: (...args: unknown[]) => requestChatCompletionStream(...args),
  stopChatTurn: (...args: unknown[]) => stopChatTurn(...args),
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
    stopGeneration: () => result.current.stopGeneration(),
    optionClick: (text: string) => result.current.handleOptionClick(text),
    phases: () => snapshots.map((s) => s.statusPhase),
    snapshots: () => snapshots,
    assistant: () => messages.find((m) => m.role === "assistant"),
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

describe("useChatStream — stopping", () => {
  beforeEach(() => vi.clearAllMocks());

  it("marks the message stopped when the done event says so", async () => {
    const stream = runStream([
      { token: "Half a sentence", done: false },
      { token: "", done: true, stopped: true, conversation_id: "conv-1" },
    ]);
    await act(async () => {
      await stream.send();
    });
    await waitFor(() => expect(stream.assistant()?.stopped).toBe(true));
  });

  it("leaves an uninterrupted message unmarked", async () => {
    const stream = runStream([
      { token: "All of it", done: false },
      { token: "", done: true, conversation_id: "conv-1" },
    ]);
    await act(async () => {
      await stream.send();
    });
    await waitFor(() => expect(stream.assistant()?.stopped).toBeFalsy());
  });

  it("sends a turn id the stop call can name", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      await stream.send();
    });
    const body = requestChatCompletionStream.mock.calls[0][1];
    expect(typeof body.turn_id).toBe("string");
    expect(body.turn_id.length).toBeGreaterThan(0);
  });

  it("stops the turn it sent, by the same turn id", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      // Fired back-to-back so the stop call runs while the turn id ref still
      // holds the id handleSend set, before the stream resolves and clears it.
      await Promise.all([stream.send(), stream.stopGeneration()]);
    });
    const body = requestChatCompletionStream.mock.calls[0][1];
    expect(stopChatTurn).toHaveBeenCalledWith("test-token", body.turn_id);
  });

  it("does nothing when no turn has been sent", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      await stream.stopGeneration();
    });
    expect(stopChatTurn).not.toHaveBeenCalled();
  });

  it("ignores an option click while a turn is still streaming", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      // An earlier message keeps its buttons on screen, so the click lands mid-turn.
      await Promise.all([stream.send(), stream.optionClick("Yes")]);
    });
    expect(requestChatCompletionStream).toHaveBeenCalledOnce();
  });

  it("sends an option click once the turn has ended", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      await stream.send();
    });
    await act(async () => {
      await stream.optionClick("Yes");
    });
    expect(requestChatCompletionStream).toHaveBeenCalledTimes(2);
  });
});
