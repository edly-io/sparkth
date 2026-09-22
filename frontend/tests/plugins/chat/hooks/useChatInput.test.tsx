import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useChatInput } from "@/plugins/chat/hooks/useChatInput";

function setup(overrides: Partial<Parameters<typeof useChatInput>[0]> = {}) {
  const onSend = vi.fn();
  const onAiKeySetupNeeded = vi.fn();
  const { result } = renderHook(() =>
    useChatInput({
      token: "test-token",
      conversationId: null,
      attachments: [],
      setAttachments: vi.fn(),
      onSend,
      onAiKeySetupNeeded,
      ...overrides,
    }),
  );
  return { result, onSend, onAiKeySetupNeeded };
}

describe("useChatInput — the AI key guard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("keeps the typed message when the guard refuses the send", async () => {
    const { result, onSend, onAiKeySetupNeeded } = setup({
      checkAiKeyReady: () => Promise.resolve("no-key" as const),
    });
    act(() => result.current.setMessage("a course about chess"));

    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).not.toHaveBeenCalled();
    expect(onAiKeySetupNeeded).toHaveBeenCalledWith("no-key");
    expect(result.current.message).toBe("a course about chess");
  });

  it("sends and clears when the guard raises no problem", async () => {
    const { result, onSend, onAiKeySetupNeeded } = setup({
      checkAiKeyReady: () => Promise.resolve(null),
    });
    act(() => result.current.setMessage("a course about chess"));

    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).toHaveBeenCalledOnce();
    expect(onAiKeySetupNeeded).not.toHaveBeenCalled();
    expect(result.current.message).toBe("");
  });

  it("sends when no guard is supplied at all", async () => {
    const { result, onSend } = setup();
    act(() => result.current.setMessage("a course about chess"));

    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).toHaveBeenCalledOnce();
  });
});
