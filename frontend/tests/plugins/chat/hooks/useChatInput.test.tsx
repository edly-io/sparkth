import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatInput } from "@/plugins/chat/hooks/useChatInput";

function setup(accepted: boolean) {
  const onSend = vi.fn(() => Promise.resolve(accepted));
  const { result } = renderHook(() =>
    useChatInput({
      token: "test-token",
      conversationId: null,
      attachments: [],
      setAttachments: vi.fn(),
      onSend,
    }),
  );
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
