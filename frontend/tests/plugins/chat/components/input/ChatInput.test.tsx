import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { ChatInput } from "@/plugins/chat/components/input/ChatInput";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

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
      />,
      chatEn,
    );

    expect(chatEn.chat.inputPlaceholder).toBeTruthy();
    expect(screen.getByPlaceholderText(chatEn.chat.inputPlaceholder)).toBeInTheDocument();
  });
});
