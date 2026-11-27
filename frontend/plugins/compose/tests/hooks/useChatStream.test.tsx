import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { getRestoredStreamData, useChatStream } from "@/plugins/compose/src/hooks/useChatStream";
import type { ChatMessage, TextAttachment } from "@/plugins/compose/src/types";

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

type AssistantSnapshot = Pick<ChatMessage, "statusPhase" | "streamedContent" | "stepLabel">;

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
        stepLabel: assistant.stepLabel,
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
    isStopping: () => result.current.isStopping,
    phases: () => snapshots.map((s) => s.statusPhase),
    snapshots: () => snapshots,
    assistant: () => messages.find((m) => m.role === "assistant"),
    replies: () => messages.filter((m) => m.role === "assistant"),
  };
}

// The chat view is not remounted when the author switches chats, so one hook serves them all.
function renderConversationHook(conversationId: string) {
  return renderHook(
    (props: { conversationId: string }) =>
      useChatStream({
        token: "test-token",
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

  it("records the generating phase the backend sends", async () => {
    const stream = runStream([{ status: "generating", done: false }]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.phases()).toContain("generating");
  });

  it("clears the phase once the first token arrives", async () => {
    const stream = runStream([
      { status: "generating", done: false },
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

const TASKS = ["Write the lesson", "Build the activity"];
const plan = (currentStep: number, hasCurrentStepRun: boolean) => ({
  tasks: TASKS,
  current_step: currentStep,
  has_current_step_run: hasCurrentStepRun,
});

describe("useChatStream — the plan and the running step", () => {
  beforeEach(() => vi.clearAllMocks());

  it("follows the plan as its steps start and run", async () => {
    const stream = runStream([
      { status: "plan", plan: plan(0, false), done: false },
      { status: "plan", plan: plan(1, false), done: false },
    ]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.assistant()?.plan).toEqual(plan(1, false));
  });

  it("keeps the plan the finished reply showed", async () => {
    const stream = runStream([
      { status: "plan", plan: plan(1, false), done: false },
      { token: "Here is the lesson.", done: false },
      { ...DONE, message: { plan: plan(1, true) } },
    ]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.assistant()?.plan).toEqual(plan(1, true));
  });

  it("names the running step while the reply is written, then drops it", async () => {
    const stream = runStream([
      { status: "step", step_status: "Working on your course design…", done: false },
      { token: "Here is the lesson.", done: false },
      DONE,
    ]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.snapshots().map((s) => s.stepLabel)).toContain("Working on your course design…");
    expect(stream.assistant()?.stepLabel).toBeUndefined();
  });

  it("shows a section while it is scanned", async () => {
    const stream = runStream([
      { status: "scanning_section", section: { type: "chapter", name: "Light" }, done: false },
    ]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.assistant()?.ragSections).toEqual([
      { type: "chapter", name: "Light", state: "scanning" },
    ]);
  });
});

describe("useChatStream — a failure partway through", () => {
  beforeEach(() => vi.clearAllMocks());

  const FAILURE = { error: "Canvas could not be reached.", done: true };

  it("keeps what was written and shows the error after it", async () => {
    const step = { status: "step", step_status: "Building your activity…", done: false };
    const stream = runStream([step, { token: "Here is the lesson.", done: false }, FAILURE]);
    await act(async () => {
      await stream.send();
    });
    const [written, failed] = stream.replies();
    expect(written).toMatchObject({ content: "Here is the lesson.", isTyping: false });
    expect(written.isError).toBeFalsy();
    expect(written.stepLabel).toBeUndefined();
    expect(failed).toMatchObject({ content: "Canvas could not be reached.", isError: true });
  });

  it("keeps the plan the written part showed", async () => {
    const stream = runStream([
      { status: "plan", plan: plan(1, false), done: false },
      { token: "Here is the lesson.", done: false },
      FAILURE,
    ]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.replies()[0].plan).toEqual(plan(1, false));
  });

  it("keeps what was written when the connection drops", async () => {
    const encoder = new TextEncoder();
    const payloads = [
      { status: "step", step_status: "Building your activity…", done: false },
      { token: "Here is the lesson.", done: false },
    ];
    // Erroring from pull lets each queued payload be read before the connection is lost.
    const queued = payloads.map((payload) =>
      encoder.encode(`data: ${JSON.stringify(payload)}\n\n`),
    );
    const dropping = new ReadableStream<Uint8Array>({
      pull(controller) {
        const next = queued.shift();
        if (next) controller.enqueue(next);
        else controller.error(new Error("The connection was lost."));
      },
    });
    const stream = runStream([]);
    requestChatCompletionStream.mockResolvedValue({ body: dropping });
    await act(async () => {
      await stream.send();
    });
    const [written, failed] = stream.replies();
    expect(written).toMatchObject({ content: "Here is the lesson.", isTyping: false });
    expect(written.stepLabel).toBeUndefined();
    expect(failed).toMatchObject({ content: "The connection was lost.", isError: true });
  });

  it("shows only the error when nothing was written", async () => {
    const stream = runStream([FAILURE]);
    await act(async () => {
      await stream.send();
    });
    expect(stream.replies()).toHaveLength(1);
    expect(stream.replies()[0]).toMatchObject({
      content: "Canvas could not be reached.",
      isError: true,
    });
  });
});

describe("useChatStream — text saved for a refresh", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("drops an earlier reply's text before the next message is sent", async () => {
    const stream = runStream([
      { token: "Half a lesson.", done: false },
      { error: "Canvas could not be reached.", done: true },
    ]);
    await act(async () => {
      await stream.send();
    });
    let savedWhenSent: unknown = "unchecked";
    requestChatCompletionStream.mockImplementation(async () => {
      savedWhenSent = getRestoredStreamData("conv-1");
      return { body: sseBody([DONE]) };
    });
    await act(async () => {
      await stream.send();
    });
    expect(savedWhenSent).toBeNull();
  });

  it("saves the text written so far", async () => {
    const stream = runStream([{ token: "Here is the lesson.", done: false }]);
    await act(async () => {
      await stream.send();
    });
    expect(getRestoredStreamData("conv-1")?.content).toBe("Here is the lesson.");
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

describe("useChatStream — files uploaded from the computer", () => {
  beforeEach(() => vi.clearAllMocks());

  async function sendWith(attachments: TextAttachment[]) {
    requestChatCompletionStream.mockResolvedValue({ body: sseBody([DONE]) });
    const { result } = renderHook(() =>
      useChatStream({
        token: "test-token",
        llmConfigId: 1,
        conversationId: "conv-1",
        setMessages: vi.fn(),
        onNewConversation: vi.fn(),
      }),
    );
    await act(async () => {
      await result.current.handleSend({ message: "Build a quiz", attachments });
    });
    return requestChatCompletionStream.mock.calls[0][1];
  }

  it("sends the typed text as the message and the files beside it", async () => {
    const body = await sendWith([{ name: "syllabus.txt", size: 13, text: "Week 1: cells" }]);

    expect(body.messages).toEqual([{ role: "user", content: "Build a quiz" }]);
    expect(body.files).toEqual([{ name: "syllabus.txt", text: "Week 1: cells" }]);
  });

  it("sends no files with a message that has none", async () => {
    const body = await sendWith([]);

    expect(body.messages).toEqual([{ role: "user", content: "Build a quiz" }]);
    expect(body).not.toHaveProperty("files");
  });
});
