import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import HistoryPanel from "@/plugins/compose/components/history/HistoryPanel";
import { useConversations } from "@/plugins/compose/hooks/useConversations";
import type { ConversationSummary } from "@/lib/compose";
import composeEn from "@/plugins/compose/messages/en.json";
import { renderWithIntl } from "../../../../intl-test-utils";

const nav = vi.hoisted(() => ({ query: "" }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.query),
}));
vi.mock("@/lib/auth/hooks", () => ({ useAuth: () => ({ token: "t" }) }));
vi.mock("@/plugins/compose/hooks/useConversations", () => ({ useConversations: vi.fn() }));

function openPanel(): void {
  renderWithIntl(<HistoryPanel />, composeEn);
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

  it("returns focus to the history button when the panel closes", async () => {
    renderWithIntl(<HistoryPanel />, composeEn);
    const button = screen.getByRole("button", { name: "Show chat history" });
    button.focus();
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Recent chats" })).toBeNull());
    expect(document.activeElement).toBe(button);
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
