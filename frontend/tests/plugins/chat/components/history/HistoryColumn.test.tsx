import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { TooltipProvider } from "@/core/components/ui/Tooltip";
import HistoryColumn from "@/plugins/chat/components/history/HistoryColumn";
import { useConversations } from "@/plugins/chat/hooks/useConversations";
import type { ConversationSummary } from "@/lib/chat";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));
vi.mock("@/plugins/chat/hooks/useConversations", () => ({ useConversations: vi.fn() }));

function renderColumn(): ReturnType<typeof renderWithIntl> {
  return renderWithIntl(
    <TooltipProvider>
      <HistoryColumn />
    </TooltipProvider>,
    chatEn,
  );
}

describe("HistoryColumn", () => {
  beforeEach(() => {
    vi.mocked(useConversations).mockReturnValue({
      conversations: [
        { id: "c-1", title: "Intro to Python", created_at: "2026-10-20T12:00:00Z" },
      ] as ConversationSummary[],
      loading: false,
      error: null,
      clearError: vi.fn(),
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("starts expanded with the list and a new-chat link", () => {
    renderColumn();

    expect(screen.getByText("Recent chats")).toBeInTheDocument();
    expect(screen.getByText("Intro to Python")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New chat" })).toHaveAttribute(
      "href",
      "/dashboard/chat",
    );
  });

  it("collapses to a rail and expands again", () => {
    renderColumn();

    fireEvent.click(screen.getByRole("button", { name: "Hide chat history" }));

    expect(screen.queryByText("Intro to Python")).toBeNull();
    expect(screen.getByRole("button", { name: "Show chat history" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New chat" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show chat history" }));

    expect(screen.getByText("Intro to Python")).toBeInTheDocument();
  });

  it("remembers the collapsed state across a remount", async () => {
    const { unmount } = renderColumn();
    fireEvent.click(screen.getByRole("button", { name: "Hide chat history" }));
    unmount();

    renderColumn();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Show chat history" })).toBeInTheDocument(),
    );
  });
});
