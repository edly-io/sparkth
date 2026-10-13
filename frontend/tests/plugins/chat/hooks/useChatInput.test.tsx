import { useState } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatInput } from "@/plugins/chat/hooks/useChatInput";
import type { TextAttachment } from "@/plugins/chat/types";

const detachDocument = vi.fn().mockResolvedValue(undefined);

vi.mock("@/lib/chat", () => ({
  attachDocument: vi.fn().mockResolvedValue(undefined),
  detachDocument: (...args: unknown[]) => detachDocument(...args),
}));

function setup(accepted: boolean) {
  const onSend = vi.fn(() => Promise.resolve(accepted));
  const { result } = renderHook(() => {
    const [message, setMessage] = useState("");
    return {
      message,
      setMessage,
      ...useChatInput({
        message,
        setMessage,
        token: "test-token",
        conversationId: null,
        attachments: [],
        setAttachments: vi.fn(),
        onSend,
      }),
    };
  });
  return { result, onSend };
}

describe("useChatInput — a refused send", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps the typed message when the send is refused", async () => {
    const { result, onSend } = setup(false);
    act(() => result.current.setMessage("a course about chess"));

    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).toHaveBeenCalledOnce();
    expect(result.current.message).toBe("a course about chess");
  });

  it("clears the message when the send is accepted", async () => {
    const { result, onSend } = setup(true);
    act(() => result.current.setMessage("a course about chess"));

    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).toHaveBeenCalledOnce();
    expect(result.current.message).toBe("");
  });
});

describe("useChatInput — removing a file uploaded from the computer", () => {
  beforeEach(() => vi.clearAllMocks());

  const first: TextAttachment = { name: "a.txt", size: 3, text: "AAA" };
  const second: TextAttachment = { name: "b.txt", size: 3, text: "BBB" };
  const drive: TextAttachment = { name: "d.pdf", size: 9, text: "[File: d.pdf]", documentId: 7 };

  function setupWith(initial: TextAttachment[]) {
    const { result } = renderHook(() => {
      const [attachments, setAttachments] = useState(initial);
      return {
        attachments,
        ...useChatInput({
          message: "",
          setMessage: vi.fn(),
          token: "test-token",
          conversationId: "conv-1",
          attachments,
          setAttachments,
          onSend: vi.fn(),
        }),
      };
    });
    return result;
  }

  it("removes only that file, leaving Drive files attached", () => {
    const result = setupWith([first, second, drive]);

    act(() => result.current.handleRemoveUpload(first));

    expect(result.current.attachments).toEqual([second, drive]);
    expect(detachDocument).not.toHaveBeenCalled();
  });

  it("removes every computer file at once, leaving Drive files attached", () => {
    const result = setupWith([first, second, drive]);

    act(() => result.current.handleRemoveUpload());

    expect(result.current.attachments).toEqual([drive]);
    expect(detachDocument).not.toHaveBeenCalled();
  });
});
