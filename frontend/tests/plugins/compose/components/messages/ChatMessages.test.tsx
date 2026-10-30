import { screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ChatMessages } from "@/plugins/compose/components/messages/ChatMessages";
import composeEn from "@/plugins/compose/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";
import type { ChatMessage } from "@/plugins/compose/types";

// jsdom has no scrollIntoView implementation; ChatMessages calls it on mount.
Element.prototype.scrollIntoView = vi.fn();

function assistant(id: string, question: string, option: string): ChatMessage {
  return { id, role: "assistant", content: `${question}\n\n\`\`\`options\n${option}\n\`\`\`` };
}

function renderMessages(messages: ChatMessage[]) {
  return renderWithIntl(
    <ChatMessages
      messages={messages}
      setPreviewOpen={vi.fn()}
      setPreviewAttachment={vi.fn()}
      onOptionCheck={vi.fn()}
    />,
    { compose: composeEn.compose },
  );
}

describe("ChatMessages — options widget", () => {
  it("only the last message's options are interactive", () => {
    renderMessages([
      assistant("a1", "Audience?", "Beginners"),
      { id: "u1", role: "user", content: "Beginners" },
      assistant("a2", "Length?", "One hour"),
    ]);
    expect(screen.getByLabelText("Beginners")).toBeDisabled();
    expect(screen.getByLabelText("One hour")).toBeEnabled();
    expect(screen.getAllByText(composeEn.compose.optionsTypeElse)).toHaveLength(1);
  });

  it("locks the widget once the user's reply is the last message", () => {
    renderMessages([
      assistant("a1", "Audience?", "Beginners"),
      { id: "u1", role: "user", content: "Beginners" },
    ]);
    expect(screen.getByLabelText("Beginners")).toBeDisabled();
    expect(screen.queryByText(composeEn.compose.optionsTypeElse)).not.toBeInTheDocument();
  });

  it("shows an answered question with the replied options checked", () => {
    renderMessages([
      assistant("a1", "Audience?", "Beginners"),
      { id: "u1", role: "user", content: "Beginners\nRetirees" },
    ]);
    expect(screen.getByLabelText("Beginners")).toBeChecked();
    expect(screen.getByLabelText("Beginners")).toBeDisabled();
    expect(screen.queryByText(composeEn.compose.optionsNoneSelected)).not.toBeInTheDocument();
  });

  it("says no option was selected when the reply matches none", () => {
    renderMessages([
      assistant("a1", "Audience?", "Beginners"),
      { id: "u1", role: "user", content: "Retirees" },
    ]);
    expect(screen.getByText(composeEn.compose.optionsNoneSelected)).toBeInTheDocument();
  });

  it("keeps each line of a multi-line user reply", () => {
    renderMessages([{ id: "u1", role: "user", content: "Beginners\nRetirees" }]);
    expect(screen.getByText("Beginners Retirees")).toHaveClass("whitespace-pre-wrap");
  });
});
