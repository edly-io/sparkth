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

  it("drops the sentence once a tool call has been recorded", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
  });

  it("shows neither the sentence nor the dots once the reply has text", () => {
    renderMessage({ content: "Here are your courses", isTyping: true });
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
    expect(screen.queryByTestId("thinking-dots")).not.toBeInTheDocument();
  });
});

describe("AssistantMessage — tool call count", () => {
  beforeEach(() => vi.clearAllMocks());

  it("counts a single running tool call while the turn streams", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "running" }],
    });
    expect(screen.getByText("1 tool call made")).toBeInTheDocument();
    // Card is suppressed when tools run with no reply text yet
    expect(screen.queryByTestId("thinking-dots")).not.toBeInTheDocument();
    expect(screen.queryByText("Working out what to do…")).not.toBeInTheDocument();
  });

  it("keeps activity visible without hovering while a tool runs", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "running" }],
    });
    expect(screen.getByTestId("tool-activity-indicator")).toBeInTheDocument();
  });

  it("keeps the card hidden between two tool calls", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.queryByTestId("thinking-dots")).not.toBeInTheDocument();
    expect(screen.getByText("1 tool call made")).toBeInTheDocument();
  });

  it("keeps the activity dot between two tool calls, while the model decides", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.getByTestId("tool-activity-indicator")).toBeInTheDocument();
  });

  it("drops the activity indicator once every tool has finished", () => {
    renderMessage({
      content: "Here are your courses",
      isTyping: false,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.queryByTestId("tool-activity-indicator")).not.toBeInTheDocument();
  });

  it("counts every call once the tools have finished and no text has arrived", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [
        { name: "moodle_create_course", status: "done" },
        { name: "moodle_create_section", status: "done" },
      ],
    });
    expect(screen.getByText("2 tool calls made")).toBeInTheDocument();
  });

  it("keeps the same count line beside the finished reply", () => {
    renderMessage({
      content: "Here are your courses",
      isTyping: false,
      toolCalls: [
        { name: "moodle_create_course", status: "done" },
        { name: "moodle_create_section", status: "done" },
      ],
    });
    expect(screen.getByText("2 tool calls made")).toBeInTheDocument();
    expect(screen.getByText("Here are your courses")).toBeInTheDocument();
    expect(screen.queryByText(/operations completed/)).not.toBeInTheDocument();
  });

  it("names every tool and marks the one still executing", () => {
    renderMessage({
      content: "",
      isTyping: true,
      toolCalls: [
        { name: "moodle_create_course", status: "done" },
        { name: "moodle_create_section", status: "running" },
      ],
    });
    expect(screen.getByText("moodle create course")).toBeInTheDocument();
    expect(screen.getByText("moodle create section")).toBeInTheDocument();
    expect(screen.getByText(/executing/)).toBeInTheDocument();
  });

  it("shows no count line when the turn called no tools", () => {
    renderMessage({ content: "Here are your courses", isTyping: false });
    expect(screen.queryByText(/tool calls? made/)).not.toBeInTheDocument();
  });

  it("keeps the record of what ran when the turn failed", () => {
    renderMessage({
      content: "An error occurred while generating a response. Please try again.",
      isTyping: false,
      isError: true,
      toolCalls: [{ name: "moodle_create_course", status: "done" }],
    });
    expect(screen.getByText("1 tool call made")).toBeInTheDocument();
    expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
  });
});
