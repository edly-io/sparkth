import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AssistantMessage } from "@/plugins/chat/components/messages/AssistantMessage";
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

describe("AssistantMessage — pending indicator", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows pulsing dot when isPending is true", () => {
    render(<AssistantMessage message={makeMessage({ isPending: true })} {...defaultProps} />);
    expect(screen.getByTestId("pending-indicator")).toBeInTheDocument();
  });

  it("does not show pulsing dot when isPending is false", () => {
    render(<AssistantMessage message={makeMessage({ isPending: false })} {...defaultProps} />);
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("does not show pulsing dot when isPending is not set", () => {
    render(<AssistantMessage message={makeMessage()} {...defaultProps} />);
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("does not show pulsing dot when isError is true even if isPending is true", () => {
    render(
      <AssistantMessage
        message={makeMessage({ isPending: true, isError: true })}
        {...defaultProps}
      />,
    );
    expect(screen.queryByTestId("pending-indicator")).not.toBeInTheDocument();
  });

  it("still renders content text when isPending is true", () => {
    render(<AssistantMessage message={makeMessage({ isPending: true })} {...defaultProps} />);
    expect(screen.getByText(/still scanning your attached files/i)).toBeInTheDocument();
  });
});
