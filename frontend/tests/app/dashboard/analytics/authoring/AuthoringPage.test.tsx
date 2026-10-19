import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "@/tests/intl-test-utils";

import { ApiRequestError } from "@/lib/api";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Analytics data access: keep the real types and helpers, stub the fetch.
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, fetchChatActivity: vi.fn() };
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/dashboard/analytics/authoring",
}));

import { CHAT_EVENTS, fetchChatActivity, type ChatActivityPoint } from "@/lib/analytics";
import AuthoringPage from "@/app/dashboard/analytics/authoring/AuthoringPage";

// Answers by period: the current period ends on the pinned "today".
function answer(current: ChatActivityPoint[], previous: ChatActivityPoint[] = []) {
  vi.mocked(fetchChatActivity).mockImplementation(async (_t, { to }) =>
    to === "2026-07-24" ? current : previous,
  );
}
const row = (
  event_type: string,
  event_count: number,
  bucket = "2026-07-23",
  extra: Partial<ChatActivityPoint> = {},
): ChatActivityPoint => ({ bucket, event_type, event_count, ...extra });
const tool = (name: string | null, count: number, outcome?: string | null) =>
  row(CHAT_EVENTS.tools, count, "2026-07-23", { dimension: name, outcome });

// Pinned so the default 30-day period is 2026-06-25..2026-07-24 and the previous one
// 2026-05-26..2026-06-24.
beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

// A card's title is a <p>; chart tables reuse some titles as column headers.
const card = async (title: string) =>
  (await screen.findByText(title, { selector: "p" })).parentElement as HTMLElement;
const empty = /no course-authoring activity in this period/i;

describe("AuthoringPage cards", () => {
  it("shows counts compared with the previous period", async () => {
    answer(
      [row(CHAT_EVENTS.conversations, 6), row(CHAT_EVENTS.messages, 10)],
      [row(CHAT_EVENTS.conversations, 4, "2026-06-20")],
    );
    renderWithIntl(<AuthoringPage />);
    const conversations = await card("Conversations started");
    expect(within(conversations).getByText("6")).toBeInTheDocument();
    expect(within(conversations).getByText("+50% vs previous period")).toBeInTheDocument();
    const messages = await card("Messages sent");
    expect(within(messages).getByText("10")).toBeInTheDocument();
    expect(within(messages).getByText("No activity in the previous period")).toBeInTheDocument();
  });

  it("shows failed turns as a share of messages", async () => {
    answer([row(CHAT_EVENTS.messages, 10), row(CHAT_EVENTS.failed, 2)]);
    renderWithIntl(<AuthoringPage />);
    const failed = await card("Messages failed");
    expect(within(failed).getByText("2")).toBeInTheDocument();
    expect(
      within(failed).getByText("20% of messages · No activity in the previous period"),
    ).toBeInTheDocument();
  });

  it("shows a dash for the failure rate when no messages were sent", async () => {
    answer([row(CHAT_EVENTS.failed, 1)]);
    renderWithIntl(<AuthoringPage />);
    expect(within(await card("Messages failed")).getByText(/^— of messages ·/)).toBeInTheDocument();
  });

  it("shows documents attached with the detached count", async () => {
    answer(
      [row(CHAT_EVENTS.attached, 3), row(CHAT_EVENTS.detached, 1)],
      [row(CHAT_EVENTS.attached, 2, "2026-06-20")],
    );
    renderWithIntl(<AuthoringPage />);
    const documents = await card("Documents attached");
    expect(within(documents).getByText("3")).toBeInTheDocument();
    expect(within(documents).getByText("1 detached · +50% vs previous period")).toBeInTheDocument();
  });

  it("notes that counts are lower bounds", async () => {
    answer([row(CHAT_EVENTS.messages, 1)]);
    renderWithIntl(<AuthoringPage />);
    expect(await screen.findByText(/counts are lower bounds/i)).toBeInTheDocument();
  });
});

describe("AuthoringPage charts", () => {
  it("draws messages sent with the previous period as the comparison", async () => {
    // 2026-06-23 is day 29 of the previous period, so it lines up with 2026-07-23.
    answer([row(CHAT_EVENTS.messages, 3)], [row(CHAT_EVENTS.messages, 7, "2026-06-23")]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Messages sent,/ });
    expect(
      within(table).getByRole("columnheader", { name: "Previous period" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 3 7" })).toBeInTheDocument();
  });

  it("draws failed turns with the previous period as the comparison", async () => {
    answer([row(CHAT_EVENTS.failed, 2)], [row(CHAT_EVENTS.failed, 5, "2026-06-23")]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Messages failed,/ });
    expect(
      within(table).getByRole("columnheader", { name: "Previous period" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 2 5" })).toBeInTheDocument();
  });

  it("draws conversations started", async () => {
    answer([row(CHAT_EVENTS.conversations, 2)]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Conversations started,/ });
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 2 0" })).toBeInTheDocument();
  });

  it("draws the failure rate as a percent, 0% where no messages were sent", async () => {
    answer([
      row(CHAT_EVENTS.messages, 4),
      row(CHAT_EVENTS.failed, 1),
      row(CHAT_EVENTS.failed, 2, "2026-07-22"),
    ]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Failure rate,/ });
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 25% 0%" })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "Jul 22, 2026 0% 0%" })).toBeInTheDocument();
  });
});

describe("AuthoringPage failure rate", () => {
  // A turn with no usable AI key fails before any message is stored, so it has no message to
  // divide by: it counts as a failed turn but stays out of the rate.
  const noKey = (count: number, bucket = "2026-07-23") =>
    row(CHAT_EVENTS.failed, count, bucket, { dimension: "llm_config_unusable" });
  const providerError = (count: number, bucket = "2026-07-23") =>
    row(CHAT_EVENTS.failed, count, bucket, { dimension: "provider_api_error" });

  it("leaves turns with no usable AI key out of the rate but in the count", async () => {
    answer([row(CHAT_EVENTS.messages, 2), providerError(1), noKey(1)]);
    renderWithIntl(<AuthoringPage />);
    const failed = await card("Messages failed");
    expect(within(failed).getByText("2")).toBeInTheDocument();
    expect(within(failed).getByText(/^50% of messages ·/)).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /^Failure rate,/ });
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 50% 0%" })).toBeInTheDocument();
  });

  it("shows no rate from failures that never reached the model", async () => {
    answer([row(CHAT_EVENTS.messages, 2), noKey(3)]);
    renderWithIntl(<AuthoringPage />);
    const failed = await card("Messages failed");
    expect(within(failed).getByText("3")).toBeInTheDocument();
    expect(within(failed).getByText(/^0% of messages ·/)).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /^Failure rate,/ });
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 0% 0%" })).toBeInTheDocument();
  });
});

describe("AuthoringPage tools", () => {
  it("ranks tools with their failures; a call with no outcome counts in the total only", async () => {
    answer([
      tool("create_course", 3, "succeeded"),
      tool("create_course", 2, "failed"),
      tool("list_courses", 1, null),
      tool("list_courses", 1),
    ]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Tool calls by tool,/ });
    expect(
      within(table).getByRole("row", { name: "create_course 5 (2 failed)" }),
    ).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "list_courses 2" })).toBeInTheDocument();
  });

  it("shows an unknown tool by its raw name, and a nameless one as a dash", async () => {
    answer([tool("brand_new_tool", 1, "succeeded"), tool(null, 1, "succeeded")]);
    renderWithIntl(<AuthoringPage />);
    const table = await screen.findByRole("table", { name: /^Tool calls by tool,/ });
    expect(within(table).getByRole("rowheader", { name: "brand_new_tool" })).toBeInTheDocument();
    expect(within(table).getByRole("rowheader", { name: "—" })).toBeInTheDocument();
  });
});

describe("AuthoringPage states", () => {
  it("shows the empty state when the period has no activity, even if the previous did", async () => {
    answer([], [row(CHAT_EVENTS.messages, 4, "2026-06-20")]);
    renderWithIntl(<AuthoringPage />);
    expect(await screen.findByText(empty)).toBeInTheDocument();
    expect(screen.queryByText("Messages sent")).not.toBeInTheDocument();
  });

  it("shows the 403 view when access is revoked", async () => {
    vi.mocked(fetchChatActivity).mockRejectedValue(
      new ApiRequestError({ message: "Permission denied", fieldErrors: {} }, 403),
    );
    renderWithIntl(<AuthoringPage />);
    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
  });

  it("re-fetches when the error state's retry button is pressed", async () => {
    answer([row(CHAT_EVENTS.messages, 1)]);
    vi.mocked(fetchChatActivity).mockRejectedValueOnce(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );
    renderWithIntl(<AuthoringPage />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Messages sent")).toBeInTheDocument();
    expect(fetchChatActivity).toHaveBeenCalledTimes(4); // two periods, twice
  });
});
