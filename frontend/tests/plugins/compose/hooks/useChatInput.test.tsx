import { useState } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, it, expect, vi, beforeEach } from "vitest";

import { useChatInput } from "@/plugins/compose/hooks/useChatInput";
import { attachDocument, detachDocument } from "@/plugins/compose/client";
import type { TextAttachment } from "@/plugins/compose/types";
import type { AttachmentSource } from "@/lib/attachments/slots";

vi.mock("@/plugins/compose/client", () => ({
  attachDocument: vi.fn(() => Promise.resolve()),
  detachDocument: vi.fn(() => Promise.resolve()),
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

function setupWithAttachments(conversationId: string | null, initial: TextAttachment[] = []) {
  const { result } = renderHook(() => {
    const [attachments, setAttachments] = useState<TextAttachment[]>(initial);
    return {
      attachments,
      ...useChatInput({
        message: "",
        setMessage: vi.fn(),
        token: "test-token",
        conversationId,
        attachments,
        setAttachments,
        onSend: vi.fn(() => Promise.resolve(true)),
      }),
    };
  });
  return { result };
}

const filesSource: AttachmentSource = {
  label: "Pick from Files",
  icon: () => null,
  loadPicker: () => Promise.resolve({ default: () => null }),
};

describe("useChatInput — documents picked from a source", () => {
  beforeEach(() => vi.clearAllMocks());
  // Puts back the console methods a test silenced.
  afterEach(() => vi.restoreAllMocks());

  it("remembers which source is being picked from", () => {
    const { result } = setupWithAttachments(null);

    act(() => result.current.setPickingFrom(filesSource));

    expect(result.current.pickingFrom).toBe(filesSource);
  });

  it("attaches the picked documents and closes the picker", () => {
    const { result } = setupWithAttachments(null);
    act(() => result.current.setPickingFrom(filesSource));

    act(() =>
      result.current.handleDocumentsSelected([{ documentId: 7, name: "notes.pdf", size: 1024 }]),
    );

    expect(result.current.attachments).toEqual([
      { name: "notes.pdf", size: 1024, text: "[File: notes.pdf]", documentId: 7 },
    ]);
    expect(result.current.pickingFrom).toBeNull();
  });

  it("attaches the picked documents to an open conversation", () => {
    const { result } = setupWithAttachments("conversation-1");

    act(() =>
      result.current.handleDocumentsSelected([{ documentId: 7, name: "notes.pdf", size: 1024 }]),
    );

    expect(attachDocument).toHaveBeenCalledWith("test-token", "conversation-1", 7);
  });

  const attachedNotes: TextAttachment = {
    name: "notes.pdf",
    size: 1024,
    text: "[File: notes.pdf]",
    documentId: 7,
  };

  it("detaches a document the user deselected", () => {
    const { result } = setupWithAttachments("conversation-1", [attachedNotes]);

    act(() => result.current.handleDocumentsSelected([]));

    expect(detachDocument).toHaveBeenCalledWith("test-token", "conversation-1", 7);
    expect(result.current.attachments).toEqual([]);
  });

  it("keeps text attachments when documents are picked", () => {
    const typed: TextAttachment = { name: "draft.txt", size: 10, text: "typed text" };
    const { result } = setupWithAttachments(null, [typed, attachedNotes]);

    act(() => result.current.handleDocumentsSelected([]));

    expect(result.current.attachments).toEqual([typed]);
  });

  it("removes a picked document again and reports it when attaching it fails", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.mocked(attachDocument).mockRejectedValueOnce(new Error("server down"));
    const { result } = setupWithAttachments("conversation-1");

    act(() =>
      result.current.handleDocumentsSelected([{ documentId: 7, name: "notes.pdf", size: 1024 }]),
    );

    await waitFor(() => expect(result.current.attachments).toEqual([]));
    expect(result.current.uploadError).toBe('Failed to attach "notes.pdf". Please try again.');
  });
});
