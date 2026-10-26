import { afterEach, describe, it, expect, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import HistoryList from "@/plugins/chat/components/history/HistoryList";
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

const mockedUseConversations = vi.mocked(useConversations);

function conversation(id: string, title: string, createdAt: string): ConversationSummary {
  return { id, title, created_at: createdAt } as ConversationSummary;
}

function stubConversations(
  conversations: ConversationSummary[],
  overrides: Partial<ReturnType<typeof useConversations>> = {},
): void {
  mockedUseConversations.mockReturnValue({
    conversations,
    loading: false,
    error: null,
    clearError: vi.fn(),
    ...overrides,
  });
}

function renderList(onNavigate?: () => void): void {
  renderWithIntl(<HistoryList onNavigate={onNavigate} />, chatEn);
}

function linkFor(title: string): HTMLElement {
  const link = screen.getByText(title).closest("a");
  if (!link) throw new Error(`no link around "${title}"`);
  return link;
}

describe("HistoryList", () => {
  afterEach(() => {
    vi.useRealTimers();
    nav.query = "";
  });

  it("links each conversation and highlights the open one", () => {
    nav.query = "id=c-2";
    stubConversations([
      conversation("c-1", "Intro to Python", "2026-10-20T12:00:00Z"),
      conversation("c-2", "Data ethics", "2026-10-19T12:00:00Z"),
    ]);

    renderList();

    const first = linkFor("Intro to Python");
    const second = linkFor("Data ethics");
    expect(first).toHaveAttribute("href", "/dashboard/chat?id=c-1");
    expect(second).toHaveAttribute("href", "/dashboard/chat?id=c-2");
    expect(second).toHaveAttribute("aria-current", "page");
    expect(first).not.toHaveAttribute("aria-current");
  });

  it("shows Untitled for a conversation without a title", () => {
    stubConversations([conversation("c-1", "", "2026-10-20T12:00:00Z")]);

    renderList();

    expect(screen.getByText("Untitled")).toBeInTheDocument();
  });

  it("labels recent dates relatively and older ones by day", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-24T12:00:00Z"));
    stubConversations([
      conversation("c-1", "A", "2026-10-24T12:00:00Z"),
      conversation("c-2", "B", "2026-10-23T12:00:00Z"),
      conversation("c-3", "C", "2026-10-21T12:00:00Z"),
      conversation("c-4", "D", "2026-10-01T12:00:00Z"),
    ]);

    renderList();

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    expect(screen.getByText("3 days ago")).toBeInTheDocument();
    expect(screen.getByText("Oct 1")).toBeInTheDocument();
  });

  it("labels a chat stamped slightly ahead of the browser clock as Today", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-24T12:00:00Z"));
    stubConversations([conversation("c-1", "A", "2026-10-24T12:00:05Z")]);

    renderList();

    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("counts calendar days, not 24-hour spans", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 24, 8, 0));
    stubConversations([
      conversation("c-1", "A", new Date(2026, 9, 23, 23, 0).toISOString()),
      conversation("c-2", "B", new Date(2026, 9, 21, 23, 0).toISOString()),
    ]);

    renderList();

    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    expect(screen.getByText("3 days ago")).toBeInTheDocument();
  });

  it("shows the empty state", () => {
    stubConversations([]);

    renderList();

    expect(screen.getByText("No previous chats")).toBeInTheDocument();
  });

  it("shows the load error and dismisses it", () => {
    const clearError = vi.fn();
    stubConversations([], { error: "x", clearError });

    renderList();

    expect(screen.getByText("Failed to load conversations. Please try again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss alert" }));
    expect(clearError).toHaveBeenCalledOnce();
  });

  it("calls onNavigate when a conversation is picked", () => {
    const onNavigate = vi.fn();
    stubConversations([conversation("c-1", "Intro to Python", "2026-10-20T12:00:00Z")]);

    renderList(onNavigate);
    fireEvent.click(linkFor("Intro to Python"));

    expect(onNavigate).toHaveBeenCalledOnce();
  });
});
