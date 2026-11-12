import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect, vi, beforeEach } from "vitest";

import { ChatInput } from "@/plugins/compose/components/input/ChatInput";
import type { AttachmentPickerProps, AttachmentSource } from "@/lib/attachments/slots";
import type { TextAttachment } from "@/plugins/compose/src/types";
import composeEn from "@/plugins/compose/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

const handleSend = vi.fn();
const setPickingFrom = vi.fn();
const setUploadError = vi.fn();
const handleDocumentsSelected = vi.fn();
// useChatInput is mocked to read this directly, so a test sets it before rendering.
let pickingFrom: AttachmentSource | null = null;

vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: () => ({ isEnabled: false, loading: false, config: {} }),
}));

vi.mock("@/plugins/compose/src/hooks/useChatInput", () => ({
  useChatInput: () => ({
    showUploadMenu: false,
    setShowUploadMenu: vi.fn(),
    pickingFrom,
    setPickingFrom,
    uploadError: null,
    setUploadError,
    handleUploadAsText: vi.fn(),
    handleDocumentsSelected,
    handleRemoveAttachment: vi.fn(),
    handleSend,
  }),
}));

describe("ChatInput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pickingFrom = null;
  });
  // Puts back console.error, which the load-failure test silences.
  afterEach(() => vi.restoreAllMocks());

  it("shows the message it is given", () => {
    renderWithIntl(
      <ChatInput
        message={"Beginners\nStudents"}
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        isStopping={false}
        onStop={vi.fn()}
      />,
      composeEn,
    );
    expect(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder)).toHaveValue(
      "Beginners\nStudents",
    );
  });

  it("reads its placeholder from the compose plugin catalog", () => {
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        isStopping={false}
        onStop={vi.fn()}
      />,
      composeEn,
    );

    expect(composeEn.compose.inputPlaceholder).toBeTruthy();
    expect(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder)).toBeInTheDocument();
  });

  it("offers a stop button while a turn is streaming", async () => {
    const onStop = vi.fn();
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming
        isStopping={false}
        onStop={onStop}
      />,
      { compose: composeEn.compose },
    );
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("stops offering the stop button once a stop is already on its way", async () => {
    const onStop = vi.fn();
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming
        isStopping
        onStop={onStop}
      />,
      { compose: composeEn.compose },
    );
    const stop = screen.getByRole("button", { name: /stop/i });
    expect(stop).toBeDisabled();
    await userEvent.click(stop);
    expect(onStop).not.toHaveBeenCalled();
  });

  it("offers the send button when nothing is streaming", () => {
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        isStopping={false}
        onStop={vi.fn()}
      />,
      { compose: composeEn.compose },
    );
    expect(screen.queryByRole("button", { name: /stop/i })).not.toBeInTheDocument();
  });

  it("does not send on Enter while a turn is streaming", () => {
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming
        isStopping={false}
        onStop={vi.fn()}
      />,
      { compose: composeEn.compose },
    );
    fireEvent.keyDown(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder), {
      key: "Enter",
    });
    expect(handleSend).not.toHaveBeenCalled();
  });

  it("sends on Enter when nothing is streaming", () => {
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={vi.fn()}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        isStopping={false}
        onStop={vi.fn()}
      />,
      { compose: composeEn.compose },
    );
    fireEvent.keyDown(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder), {
      key: "Enter",
    });
    expect(handleSend).toHaveBeenCalledOnce();
  });

  it("passes edits to setMessage", () => {
    const setMessage = vi.fn();
    renderWithIntl(
      <ChatInput
        message=""
        setMessage={setMessage}
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        isStopping={false}
        onStop={vi.fn()}
      />,
      composeEn,
    );
    fireEvent.change(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder), {
      target: { value: "Beginners" },
    });
    expect(setMessage).toHaveBeenCalledWith("Beginners");
  });

  describe("picking documents from a source", () => {
    const picked = { documentId: 8, name: "slides.pdf", size: 2048 };

    function FilesPicker({ selected, onSelect, onClose }: AttachmentPickerProps) {
      return (
        <div>
          <p>Selected: {selected.map((document) => document.name).join(", ")}</p>
          <button onClick={() => onSelect([picked])}>Attach</button>
          <button onClick={() => onClose()}>Cancel</button>
        </div>
      );
    }

    function pickFrom(loadPicker: AttachmentSource["loadPicker"]) {
      pickingFrom = { label: "Pick from Files", icon: () => null, loadPicker };
    }

    const attachments: TextAttachment[] = [
      // Restored from the conversation: it carries only its document id.
      { name: "notes.pdf", size: 1024, text: "[File: notes.pdf]", documentId: 7 },
      { name: "draft.txt", size: 10, text: "typed text" },
    ];

    function renderInput() {
      renderWithIntl(
        <ChatInput
          message=""
          setMessage={vi.fn()}
          attachments={attachments}
          setAttachments={vi.fn()}
          onSend={vi.fn()}
          conversationId={null}
          isStreaming={false}
          isStopping={false}
          onStop={vi.fn()}
        />,
        composeEn,
      );
    }

    it("opens the chosen source's picker with the documents already attached", async () => {
      pickFrom(() => Promise.resolve({ default: FilesPicker }));
      renderInput();

      expect(await screen.findByText("Selected: notes.pdf")).toBeInTheDocument();
    });

    it("attaches the documents the picker hands back", async () => {
      pickFrom(() => Promise.resolve({ default: FilesPicker }));
      renderInput();

      await userEvent.click(await screen.findByRole("button", { name: "Attach" }));

      expect(handleDocumentsSelected).toHaveBeenCalledWith([picked]);
    });

    it("closes the picker when the picker closes", async () => {
      pickFrom(() => Promise.resolve({ default: FilesPicker }));
      renderInput();

      await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));

      expect(setPickingFrom).toHaveBeenCalledWith(null);
    });

    it("keeps the input and reports an error when the picker fails to load", async () => {
      // React logs the error the boundary catches; keep the test output clean.
      vi.spyOn(console, "error").mockImplementation(() => {});
      pickFrom(() => Promise.reject(new Error("chunk failed")));
      renderInput();

      await waitFor(() => expect(setPickingFrom).toHaveBeenCalledWith(null));
      expect(setUploadError).toHaveBeenCalledWith(composeEn.compose.pickerFailed);
      expect(screen.getByPlaceholderText(composeEn.compose.inputPlaceholder)).toBeInTheDocument();
    });

    it("shows no picker while no source is chosen", () => {
      renderInput();

      expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument();
    });
  });
});
