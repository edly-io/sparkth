import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import HistoryPanel from "@/plugins/chat/components/history/HistoryPanel";
import { useConversations } from "@/plugins/chat/hooks/useConversations";
import type { ConversationSummary } from "@/lib/chat";
import chatEn from "@/plugins/chat/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

const nav = vi.hoisted(() => ({ query: "" }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.query),
}));
vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));
vi.mock("@/plugins/chat/hooks/useConversations", () => ({ useConversations: vi.fn() }));

function openPanel(): void {
  renderWithIntl(<HistoryPanel />, chatEn);
  fireEvent.click(screen.getByRole("button", { name: "Show chat history" }));
}

function pickConversation(title: string): void {
  const link = screen.getByText(title).closest("a");
  if (!link) throw new Error(`no link around "${title}"`);
  fireEvent.click(link);
}

describe("HistoryPanel", () => {
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
    nav.query = "";
  });

  it("opens the history panel from the header button", () => {
    openPanel();

    expect(screen.getByRole("heading", { name: "Recent chats" })).toBeInTheDocument();
    expect(screen.getByText("Intro to Python")).toBeInTheDocument();
  });

  it("closes the panel when a chat is picked", async () => {
    openPanel();

    pickConversation("Intro to Python");

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Recent chats" })).toBeNull());
  });

  it("closes the panel when the open chat is picked again", async () => {
    nav.query = "id=c-1";
    openPanel();

    pickConversation("Intro to Python");

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Recent chats" })).toBeNull());
  });
});
