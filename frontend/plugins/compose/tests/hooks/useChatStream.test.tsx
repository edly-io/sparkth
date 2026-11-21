import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatStream } from "@/plugins/compose/src/hooks/useChatStream";
import { addStoredFiles, getStoredFiles } from "@/plugins/compose/src/storedFiles";
import type { ChatMessage } from "@/plugins/compose/src/types";

const requestChatCompletionStream = vi.fn();
const stopChatTurn = vi.fn().mockResolvedValue(undefined);

vi.mock("@/plugins/compose/src/client", () => ({
  requestChatCompletionStream: (...args: unknown[]) => requestChatCompletionStream(...args),
  stopChatTurn: (...args: unknown[]) => stopChatTurn(...args),
}));

// Serves the payloads exactly as sparkth/plugins/compose/routes/utils/stream_processor.py writes
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
      userId: 7,
      llmConfigId: 1,
      conversationId: "conv-1",
      setMessages,
      onNewConversation: vi.fn(),
    }),
  );
  return {
    send: () => result.current.handleSend({ message: "hello", attachments: [] }),
    stopGeneration: () => result.current.stopGeneration(),
    isStopping: () => result.current.isStopping,
    phases: () => snapshots.map((s) => s.statusPhase),
    snapshots: () => snapshots,
    assistant: () => messages.find((m) => m.role === "assistant"),
  };
}

// The chat view is not remounted when the author switches chats, so one hook serves them all.
function renderConversationHook(conversationId: string) {
  return renderHook(
    (props: { conversationId: string }) =>
      useChatStream({
        token: "test-token",
        userId: 7,
        llmConfigId: 1,
        conversationId: props.conversationId,
        setMessages: vi.fn(),
        onNewConversation: vi.fn(),
      }),
    { initialProps: { conversationId } },
  );
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

  it("clears the stopping flag once the turn has ended", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      await Promise.all([stream.send(), stream.stopGeneration()]);
    });
    expect(stream.isStopping()).toBe(false);
  });

  it("does not enter the stopping state when no turn is live", async () => {
    const stream = runStream([{ token: "", done: true, conversation_id: "conv-1" }]);
    await act(async () => {
      await stream.stopGeneration();
    });
    expect(stream.isStopping()).toBe(false);
  });
});

describe("useChatStream — one turn at a time", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends one request when send fires again before the turn ends", async () => {
    const stream = runStream([DONE]);
    await act(async () => {
      await Promise.all([stream.send(), stream.send(), stream.send()]);
    });
    expect(requestChatCompletionStream).toHaveBeenCalledTimes(1);
  });

  it("sends again once the turn has ended", async () => {
    const stream = runStream([DONE]);
    await act(async () => {
      await stream.send();
    });
    await act(async () => {
      await stream.send();
    });
    expect(requestChatCompletionStream).toHaveBeenCalledTimes(2);
  });

  it("sends in another conversation while the first one's turn is still running", async () => {
    requestChatCompletionStream.mockReturnValue(new Promise(() => {}));
    const hook = renderConversationHook("conv-1");
    act(() => {
      void hook.result.current.handleSend({ message: "first", attachments: [] });
    });

    hook.rerender({ conversationId: "conv-2" });
    act(() => {
      void hook.result.current.handleSend({ message: "second", attachments: [] });
    });

    expect(requestChatCompletionStream).toHaveBeenCalledTimes(2);
  });

  it("keeps the other conversation's turn live when the first one ends", async () => {
    let finishFirst!: (value: { body: ReadableStream<Uint8Array> }) => void;
    requestChatCompletionStream
      .mockReturnValueOnce(new Promise((resolve) => (finishFirst = resolve)))
      .mockReturnValueOnce(new Promise(() => {}));
    const hook = renderConversationHook("conv-1");
    act(() => {
      void hook.result.current.handleSend({ message: "first", attachments: [] });
    });
    hook.rerender({ conversationId: "conv-2" });
    act(() => {
      void hook.result.current.handleSend({ message: "second", attachments: [] });
    });

    await act(async () => finishFirst({ body: sseBody([DONE]) }));
    await act(async () => {
      await hook.result.current.stopGeneration();
    });

    const secondTurnId = requestChatCompletionStream.mock.calls[1][1].turn_id;
    expect(stopChatTurn).toHaveBeenCalledWith("test-token", secondTurnId);
  });

  it("reports a turn live only in the conversation that sent it", async () => {
    requestChatCompletionStream.mockReturnValue(new Promise(() => {}));
    const hook = renderConversationHook("conv-1");
    act(() => {
      void hook.result.current.handleSend({ message: "first", attachments: [] });
    });
    expect(hook.result.current.isTurnLive()).toBe(true);

    hook.rerender({ conversationId: "conv-2" });
    expect(hook.result.current.isTurnLive()).toBe(false);
  });

  it("sends again after a response that had no body", async () => {
    const stream = runStream([DONE]);
    requestChatCompletionStream.mockResolvedValue({ body: null });
    await act(async () => {
      await stream.send();
    });
    await act(async () => {
      await stream.send();
    });
    expect(requestChatCompletionStream).toHaveBeenCalledTimes(2);
  });
});

describe("useChatStream — uploaded files", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const syllabus = { name: "syllabus.txt", size: 12, text: "Week 1: cells" };

  function sendWithFiles(conversationId: string | null, attachments = [syllabus]) {
    const { result } = renderHook(() =>
      useChatStream({
        token: "test-token",
        userId: 7,
        llmConfigId: 1,
        conversationId,
        setMessages: vi.fn(),
        onNewConversation: vi.fn(),
      }),
    );
    return act(async () => {
      await result.current.handleSend({ message: "Build a quiz", attachments });
    });
  }

  it("sends the typed text as the turn and the file's text beside it", async () => {
    requestChatCompletionStream.mockResolvedValue({ body: sseBody([DONE]) });

    await sendWithFiles("conv-1");

    const body = requestChatCompletionStream.mock.calls[0][1];
    expect(body.messages).toEqual([{ role: "user", content: "Build a quiz" }]);
    expect(body.files).toEqual([{ name: "syllabus.txt", text: "Week 1: cells" }]);
  });

  it("sends the files kept from earlier turns with each turn", async () => {
    addStoredFiles(7, "conv-1", [{ name: "notes.txt", size: 5, text: "mitochondria" }]);
    requestChatCompletionStream.mockResolvedValue({ body: sseBody([DONE]) });

    await sendWithFiles("conv-1", []);

    const body = requestChatCompletionStream.mock.calls[0][1];
    expect(body.files).toEqual([{ name: "notes.txt", text: "mitochondria" }]);
  });

  it("keeps a new conversation's files under the id its reply names", async () => {
    requestChatCompletionStream.mockResolvedValue({
      body: sseBody([{ token: "", done: true, conversation_id: "conv-new" }]),
    });

    await sendWithFiles(null);

    expect(getStoredFiles(7, "conv-new")).toEqual([syllabus]);
  });

  it("keeps the files when the reply fails, since the turn was stored", async () => {
    requestChatCompletionStream.mockResolvedValue({
      body: sseBody([{ error: "The model is overloaded.", done: true }]),
    });

    await sendWithFiles("conv-1");

    expect(getStoredFiles(7, "conv-1")).toEqual([syllabus]);
  });
});
