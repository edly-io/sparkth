import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ChatInput } from "@/plugins/compose/components/input/ChatInput";
import composeEn from "@/plugins/compose/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

const handleSend = vi.fn();

vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/plugins/context", () => ({
  usePlugin: () => ({ isEnabled: false, loading: false, config: {} }),
}));

vi.mock("@/components/drive/DriveFilePicker", () => ({
  default: () => null,
}));

vi.mock("@/plugins/compose/hooks/useChatInput", () => ({
  useChatInput: () => ({
    showUploadMenu: false,
    setShowUploadMenu: vi.fn(),
    showDriveFilePicker: false,
    setShowDriveFilePicker: vi.fn(),
    uploadError: null,
    setUploadError: vi.fn(),
    handleUploadAsText: vi.fn(),
    handleDriveFileSelected: vi.fn(),
    handleRemoveAttachment: vi.fn(),
    handleSend,
  }),
}));

describe("ChatInput", () => {
  beforeEach(() => handleSend.mockClear());

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
});
