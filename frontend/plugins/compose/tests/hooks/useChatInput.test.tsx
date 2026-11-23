import { useState, type ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, it, expect, vi, beforeEach } from "vitest";

import { useChatInput } from "@/plugins/compose/src/hooks/useChatInput";
import {
  attachDocument,
  detachDocument,
  removeConversationUploadedFile,
} from "@/plugins/compose/src/client";
import type { TextAttachment } from "@/plugins/compose/src/types";
import { uploadFile, type UploadResponse } from "@/plugins/compose/src/upload";
import { ATTACHMENT_SOURCES, type AttachmentSource } from "@/plugins/compose/src/slots/attachments";
import composeEn from "@/plugins/compose/src/i18n/en.json";
import { IntlTestProvider } from "@/lib/testing/intl";

vi.mock("@/plugins/compose/src/client", () => ({
  attachDocument: vi.fn(() => Promise.resolve()),
  detachDocument: vi.fn(() => Promise.resolve()),
  removeConversationUploadedFile: vi.fn(() => Promise.resolve()),
}));

vi.mock("@/plugins/compose/src/upload", () => ({
  uploadFile: vi.fn(() => Promise.resolve({ filename: "notes.txt", length: 5, text: "Week 1" })),
}));

function wrapper({ children }: { children: ReactNode }) {
  return <IntlTestProvider messages={composeEn}>{children}</IntlTestProvider>;
}

function setup(accepted: boolean) {
  const onSend = vi.fn(() => Promise.resolve(accepted));
  const { result } = renderHook(
    () => {
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
    },
    { wrapper },
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

function setupWithAttachments(conversationId: string | null, initial: TextAttachment[] = []) {
  const { result } = renderHook(
    () => {
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
    },
    { wrapper },
  );
  return { result };
}

const filesSource: AttachmentSource = {
  id: "files-source",
  label: "Pick from Files",
  icon: () => null,
  loadPicker: () => Promise.resolve({ default: () => null }),
};

describe("useChatInput — documents picked from a source", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ATTACHMENT_SOURCES.clear();
    ATTACHMENT_SOURCES.set("files-plugin", [filesSource]);
  });
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
      {
        name: "notes.pdf",
        size: 1024,
        documentId: 7,
        source: "files-source",
      },
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
    documentId: 7,
  };

  it("detaches a document the user deselected", () => {
    const { result } = setupWithAttachments("conversation-1", [attachedNotes]);

    act(() => result.current.handleDocumentsSelected([]));

    expect(detachDocument).toHaveBeenCalledWith("test-token", "conversation-1", 7);
    expect(result.current.attachments).toEqual([]);
  });

  it("keeps the source of a document picked again", () => {
    const { result } = setupWithAttachments(null, [{ ...attachedNotes, source: "drive-source" }]);
    act(() => result.current.setPickingFrom(filesSource));

    act(() =>
      result.current.handleDocumentsSelected([{ documentId: 7, name: "notes.pdf", size: 1024 }]),
    );

    expect(result.current.attachments[0].source).toBe("drive-source");
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

describe("useChatInput — files uploaded from the computer", () => {
  beforeEach(() => vi.clearAllMocks());

  const attachedDocument: TextAttachment = {
    name: "drive.pdf",
    size: 1024,
    documentId: 7,
  };

  it("adds an uploaded file with its own upload id", async () => {
    const { result } = setupWithAttachments(null);

    await act(async () => {
      await result.current.handleUploadFromComputer([new File(["Week 1"], "notes.txt")]);
    });

    expect(result.current.attachments).toEqual([
      {
        name: "notes.txt",
        size: 6,
        text: "Week 1",
        uploadId: expect.any(String),
        isUploading: false,
      },
    ]);
  });

  it("lists a file as uploading until its upload finishes", async () => {
    let finishUpload: (response: UploadResponse) => void = () => {};
    vi.mocked(uploadFile).mockReturnValueOnce(
      new Promise((resolve) => {
        finishUpload = resolve;
      }),
    );
    const { result } = setupWithAttachments(null);

    let upload: Promise<void> = Promise.resolve();
    act(() => {
      upload = result.current.handleUploadFromComputer([new File(["Week 1"], "notes.txt")]);
    });

    expect(result.current.attachments).toEqual([
      { name: "notes.txt", size: 6, uploadId: expect.any(String), isUploading: true },
    ]);

    await act(async () => {
      finishUpload({ filename: "notes.txt", length: 6, text: "Week 1" });
      await upload;
    });

    expect(result.current.attachments[0]).toMatchObject({ text: "Week 1", isUploading: false });
  });

  it("cancels a file's upload when it is removed while uploading", async () => {
    let failUpload: (error: Error) => void = () => {};
    vi.mocked(uploadFile).mockReturnValueOnce(
      new Promise((_, reject) => {
        failUpload = reject;
      }),
    );
    const { result } = setupWithAttachments(null);
    let upload: Promise<void> = Promise.resolve();
    act(() => {
      upload = result.current.handleUploadFromComputer([new File(["Week 1"], "notes.txt")]);
    });
    const signal = vi.mocked(uploadFile).mock.calls[0][2];

    act(() => result.current.handleRemoveAttachment(result.current.attachments[0]));
    await act(async () => {
      failUpload(new DOMException("The operation was aborted.", "AbortError"));
      await upload;
    });

    expect(signal?.aborted).toBe(true);
    expect(result.current.attachments).toEqual([]);
    expect(result.current.uploadError).toBeNull();
  });

  it("removes a file whose upload fails and reports the error", async () => {
    vi.mocked(uploadFile).mockRejectedValueOnce(
      new Error("Only .txt and .pdf files are supported"),
    );
    const { result } = setupWithAttachments(null);

    await act(async () => {
      await result.current.handleUploadFromComputer([new File(["x"], "notes.docx")]);
    });

    expect(result.current.attachments).toEqual([]);
    expect(result.current.uploadError).toBe(
      'Failed to upload "notes.docx": Only .txt and .pdf files are supported',
    );
  });

  it("removes a sent file from the conversation on the server too", () => {
    const sentFile: TextAttachment = {
      name: "notes.txt",
      size: 6,
      uploadId: "uploaded-notes.txt",
      isSent: true,
    };
    const { result } = setupWithAttachments("conversation-1", [sentFile]);

    act(() => result.current.handleRemoveAttachment(sentFile));

    expect(removeConversationUploadedFile).toHaveBeenCalledWith(
      "test-token",
      "conversation-1",
      "notes.txt",
    );
    expect(result.current.attachments).toEqual([]);
  });

  it("lists a sent file again and reports it when removing it fails", async () => {
    vi.mocked(removeConversationUploadedFile).mockRejectedValueOnce(new Error("server down"));
    const sentFile: TextAttachment = {
      name: "notes.txt",
      size: 6,
      uploadId: "uploaded-notes.txt",
      isSent: true,
    };
    const { result } = setupWithAttachments("conversation-1", [sentFile]);

    act(() => result.current.handleRemoveAttachment(sentFile));

    await waitFor(() => expect(result.current.attachments).toEqual([sentFile]));
    expect(result.current.uploadError).toBe('Failed to detach "notes.txt". Please try again.');
  });

  it("removes only the uploaded file and leaves documents attached", async () => {
    const { result } = setupWithAttachments("conversation-1", [attachedDocument]);
    await act(async () => {
      await result.current.handleUploadFromComputer([new File(["Week 1"], "notes.txt")]);
    });
    const uploadedFile = result.current.attachments[1];

    act(() => result.current.handleRemoveAttachment(uploadedFile));

    expect(result.current.attachments).toEqual([attachedDocument]);
    expect(detachDocument).not.toHaveBeenCalled();
    expect(removeConversationUploadedFile).not.toHaveBeenCalled();
  });

  it("detaches a removed document from the conversation", () => {
    const { result } = setupWithAttachments("conversation-1", [attachedDocument]);

    act(() => result.current.handleRemoveAttachment(attachedDocument));

    expect(result.current.attachments).toEqual([]);
    expect(detachDocument).toHaveBeenCalledWith("test-token", "conversation-1", 7);
  });
});

describe("useChatInput — picking several files from the computer", () => {
  beforeEach(() => vi.clearAllMocks());

  const MB = 1024 * 1024;
  const fileOfSize = (name: string, bytes: number) => new File([new Uint8Array(bytes)], name);
  const listedFile = (name: string, size: number): TextAttachment => ({
    name,
    size,
    text: "Week 1",
    uploadId: `upload-${name}`,
  });

  it("uploads every picked file", async () => {
    const { result } = setupWithAttachments(null);

    await act(async () => {
      await result.current.handleUploadFromComputer([
        new File(["Week 1"], "notes.txt"),
        new File(["Week 2"], "outline.txt"),
      ]);
    });

    expect(uploadFile).toHaveBeenCalledTimes(2);
    expect(result.current.attachments.map((a) => [a.name, a.isUploading])).toEqual([
      ["notes.txt", false],
      ["outline.txt", false],
    ]);
  });

  it("rejects the whole selection when it goes over 3 MB", async () => {
    const { result } = setupWithAttachments(null);

    await act(async () => {
      await result.current.handleUploadFromComputer([
        fileOfSize("week1.pdf", 2 * MB),
        fileOfSize("week2.pdf", 2 * MB),
      ]);
    });

    expect(uploadFile).not.toHaveBeenCalled();
    expect(result.current.attachments).toEqual([]);
    expect(result.current.uploadError).toBe(
      "These files would take the conversation over its 3 MB limit.",
    );
  });

  it("counts uploads already sent toward the limit", async () => {
    const { result } = setupWithAttachments(null, [
      { ...listedFile("week1.pdf", 2 * MB), isSent: true },
    ]);

    await act(async () => {
      await result.current.handleUploadFromComputer([fileOfSize("week2.pdf", 2 * MB)]);
    });

    expect(uploadFile).not.toHaveBeenCalled();
    expect(result.current.uploadError).toBe(
      "These files would take the conversation over its 3 MB limit.",
    );
  });

  it("does not count documents toward the limit", async () => {
    const { result } = setupWithAttachments(null, [
      { name: "drive.pdf", size: 5 * MB, documentId: 7 },
    ]);

    await act(async () => {
      await result.current.handleUploadFromComputer([fileOfSize("week2.pdf", 2 * MB)]);
    });

    expect(uploadFile).toHaveBeenCalledOnce();
    expect(result.current.uploadError).toBeNull();
  });

  it("skips a file with a listed file's name, whatever its size", async () => {
    const { result } = setupWithAttachments(null, [
      { ...listedFile("notes.txt", 999), isSent: true },
    ]);

    await act(async () => {
      await result.current.handleUploadFromComputer([new File(["Week 1"], "notes.txt")]);
    });

    expect(uploadFile).not.toHaveBeenCalled();
    expect(result.current.uploadError).toBe("File already attached.");
  });

  it("skips a file already listed, even one already sent, and says so", async () => {
    const { result } = setupWithAttachments(null, [
      { ...listedFile("notes.txt", 6), isSent: true },
    ]);

    await act(async () => {
      await result.current.handleUploadFromComputer([
        new File(["Week 1"], "notes.txt"),
        new File(["Week 2"], "outline.txt"),
      ]);
    });

    expect(uploadFile).toHaveBeenCalledOnce();
    expect(result.current.attachments.map((a) => a.name)).toEqual(["notes.txt", "outline.txt"]);
    expect(result.current.uploadError).toBe("File already attached.");
  });
});

describe("useChatInput — sending computer uploads", () => {
  beforeEach(() => vi.clearAllMocks());

  const uploadedNotes: TextAttachment = {
    name: "notes.txt",
    size: 6,
    text: "Week 1",
    uploadId: "upload-1",
  };

  function setupSend(initial: TextAttachment[]) {
    const onSend = vi.fn(() => Promise.resolve(true));
    const { result } = renderHook(
      () => {
        const [attachments, setAttachments] = useState<TextAttachment[]>(initial);
        return {
          attachments,
          ...useChatInput({
            message: "Summarise this",
            setMessage: vi.fn(),
            token: "test-token",
            conversationId: "conversation-1",
            attachments,
            setAttachments,
            onSend,
          }),
        };
      },
      { wrapper },
    );
    return { result, onSend };
  }

  it("keeps a sent upload listed and marks it as sent", async () => {
    const { result } = setupSend([uploadedNotes]);

    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.attachments).toEqual([{ ...uploadedNotes, isSent: true }]);
  });

  it("does not send an upload again with the next message", async () => {
    const { result, onSend } = setupSend([uploadedNotes]);

    await act(async () => {
      await result.current.handleSend();
    });
    await act(async () => {
      await result.current.handleSend();
    });

    expect(onSend).toHaveBeenLastCalledWith({ message: "Summarise this", attachments: [] });
  });
});

describe("useChatInput — when a message can be sent", () => {
  beforeEach(() => vi.clearAllMocks());

  function setupCanSend(message: string, attachments: TextAttachment[]) {
    const onSend = vi.fn(() => Promise.resolve(true));
    const { result } = renderHook(
      () =>
        useChatInput({
          message,
          setMessage: vi.fn(),
          token: "test-token",
          conversationId: null,
          attachments,
          setAttachments: vi.fn(),
          onSend,
        }),
      { wrapper },
    );
    return { result, onSend };
  }

  const uploadedNotes: TextAttachment = {
    name: "notes.txt",
    size: 6,
    text: "Week 1",
    uploadId: "upload-1",
  };

  it("can send once a message is typed", () => {
    const { result } = setupCanSend("Summarise this", [uploadedNotes]);

    expect(result.current.canSend).toBe(true);
  });

  it("cannot send files without a typed message", async () => {
    const { result, onSend } = setupCanSend("  ", [uploadedNotes]);

    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.canSend).toBe(false);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("cannot send while a file is still uploading", async () => {
    const { result, onSend } = setupCanSend("Summarise this", [
      { ...uploadedNotes, isUploading: true },
    ]);

    await act(async () => {
      await result.current.handleSend();
    });

    expect(result.current.canSend).toBe(false);
    expect(onSend).not.toHaveBeenCalled();
  });
});
