import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AssistantMessage } from "@/plugins/chat/components/messages/AssistantMessage";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";
import type { ChatMessage } from "@/plugins/chat/types";

const defaultProps = {
  setPreviewOpen: vi.fn(),
  setPreviewAttachment: vi.fn(),
  onOptionClick: vi.fn(),
};

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content: "Still scanning your attached files — this may take a moment.",
    ...overrides,
  };
}

function renderMessage(overrides: Partial<ChatMessage> = {}) {
  return renderWithIntl(<AssistantMessage message={makeMessage(overrides)} {...defaultProps} />, {
    chat: chatEn.chat,
  });
}

describe("AssistantMessage — pending indicator", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows pulsing dot when isPending is true", () => {
    renderMessage({ isPending: true });
    expect(screen.getByTestId("pending-indicator")).toBeInTheDocument();
  });

  it("does not show pulsing dot when isPending is false", () => {
    renderMessage({ isPending: false });
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("does not show pulsing dot when isPending is not set", () => {
    renderMessage();
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("does not show pulsing dot when isError is true even if isPending is true", () => {
    renderMessage({ isPending: true, isError: true });
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("still renders content text when isPending is true", () => {
    renderMessage({ isPending: true });
    expect(screen.getByText(/still scanning your attached files/i)).toBeInTheDocument();
  });
});

describe("AssistantMessage — status sentence", () => {
  beforeEach(() => vi.clearAllMocks());

  it("says what it is doing while streaming with no text and no tool calls", () => {
    renderMessage({ content: "", isTyping: true });
    expect(screen.getByText("Working out what to do…")).toBeInTheDocument();
  });

  it("keeps a backend-supplied status over the default sentence", () => {
    renderMessage({ content: "", isTyping: true, statusText: "Scanning document sections..." });
    expect(screen.getByText("Scanning document sections...")).toBeInTheDocument();
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
  });

  it("drops the sentence for bouncing dots once a tool call has been recorded", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
    expect(screen.getByTestId("thinking-dots")).toBeInTheDocument();
  });

  it("shows neither the sentence nor the dots once the reply has text", () => {
    renderMessage({ content: "Here are your courses", isTyping: true });
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
    expect(screen.queryByTestId("thinking-dots")).not.toBeInTheDocument();
  });
});
