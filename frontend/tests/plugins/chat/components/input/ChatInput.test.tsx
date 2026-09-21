import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { ChatInput } from "@/plugins/chat/components/input/ChatInput";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/lib/plugins/usePlugins", () => ({
  useIsPluginEnabled: () => false,
}));

vi.mock("@/components/drive/DriveFilePicker", () => ({
  default: () => null,
}));

vi.mock("@/plugins/chat/hooks/useChatInput", () => ({
  useChatInput: () => ({
    message: "",
    setMessage: vi.fn(),
    showUploadMenu: false,
    setShowUploadMenu: vi.fn(),
    showDriveFilePicker: false,
    setShowDriveFilePicker: vi.fn(),
    uploadError: null,
    setUploadError: vi.fn(),
    handleUploadAsText: vi.fn(),
    handleDriveFileSelected: vi.fn(),
    handleRemoveAttachment: vi.fn(),
    handleSend: vi.fn(),
  }),
}));

describe("ChatInput", () => {
  it("reads its placeholder from the chat plugin catalog", () => {
    renderWithIntl(
      <ChatInput
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        onStop={vi.fn()}
      />,
      chatEn,
    );

    expect(chatEn.chat.inputPlaceholder).toBeTruthy();
    expect(screen.getByPlaceholderText(chatEn.chat.inputPlaceholder)).toBeInTheDocument();
  });

  it("offers a stop button while a turn is streaming", async () => {
    const onStop = vi.fn();
    renderWithIntl(
      <ChatInput
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming
        onStop={onStop}
      />,
      { chat: chatEn.chat },
    );
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalledOnce();
  });

  it("offers the send button when nothing is streaming", () => {
    renderWithIntl(
      <ChatInput
        attachments={[]}
        setAttachments={vi.fn()}
        onSend={vi.fn()}
        conversationId={null}
        isStreaming={false}
        onStop={vi.fn()}
      />,
      { chat: chatEn.chat },
    );
    expect(screen.queryByRole("button", { name: /stop/i })).not.toBeInTheDocument();
  });
});
