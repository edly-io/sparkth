import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { TooltipProvider } from "@/core/components/ui/Tooltip";
import HistoryColumn from "@/plugins/compose/components/history/HistoryColumn";
import { useConversations } from "@/plugins/compose/hooks/useConversations";
import { HISTORY_COLLAPSED_KEY } from "@/plugins/compose/hooks/useHistoryCollapsed";
import type { ConversationSummary } from "@/lib/compose";
import composeEn from "@/plugins/compose/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));
vi.mock("@/plugins/compose/hooks/useConversations", () => ({ useConversations: vi.fn() }));

function renderColumn(): ReturnType<typeof renderWithIntl> {
  return renderWithIntl(
    <TooltipProvider>
      <HistoryColumn />
    </TooltipProvider>,
    composeEn,
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
      "/dashboard/compose",
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

  it("keeps keyboard focus on the toggle when collapsing and expanding", () => {
    renderColumn();
    const hide = screen.getByRole("button", { name: "Hide chat history" });
    hide.focus();

    fireEvent.click(hide);
    const show = screen.getByRole("button", { name: "Show chat history" });
    expect(document.activeElement).toBe(show);

    fireEvent.click(show);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Hide chat history" }));
  });

  it("shows a tooltip on each rail action", async () => {
    localStorage.setItem(HISTORY_COLLAPSED_KEY, "true");
    renderColumn();
    const show = await screen.findByRole("button", { name: "Show chat history" });

    fireEvent.focus(show);
    expect((await screen.findAllByText("Show chat history")).length).toBeGreaterThan(0);

    fireEvent.blur(show);
    fireEvent.focus(screen.getByRole("link", { name: "New chat" }));
    expect((await screen.findAllByText("New chat")).length).toBeGreaterThan(0);
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
