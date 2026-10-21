import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Analytics data access: keep the real helpers, stub the fetches.
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, fetchEventCatalog: vi.fn(), fetchExplore: vi.fn() };
});

const access = vi.hoisted(() => ({ userRead: "allowed" }));
vi.mock("@/lib/permissions", () => ({ usePermissionCheck: () => access.userRead }));

const nav = vi.hoisted(() => ({ search: "", replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => ({ replace: nav.replace }),
  usePathname: () => "/dashboard/analytics/explore",
}));

import {
  fetchEventCatalog,
  fetchExplore,
  type EventCatalogEntry,
  type ExploreResult,
} from "@/lib/analytics";
import ExplorePage from "@/app/dashboard/analytics/explore/ExplorePage";
import { PeriodSelector } from "@/app/dashboard/analytics/PeriodSelector";

const catalog: EventCatalogEntry[] = [
  {
    event_type: "chat.tool_invoked",
    fields: [
      { name: "outcome", kind: "enum", values: ["ok", "provider_api_error"], nullable: true },
      { name: "tool", kind: "string", values: null, nullable: false },
      { name: "attempts", kind: "integer", values: null, nullable: false },
    ],
  },
  { event_type: "auth.login", fields: [] },
];

function answer(result: Partial<ExploreResult>) {
  vi.mocked(fetchExplore).mockResolvedValue({
    points: [],
    totals: [],
    truncated: false,
    actor_names: {},
    ...result,
  });
}

// Pinned so the default 30-day period is 2026-06-25..2026-07-24.
beforeEach(() => {
  vi.clearAllMocks();
  nav.search = "";
  access.userRead = "allowed";
  vi.mocked(fetchEventCatalog).mockResolvedValue(catalog);
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-07-24T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ExplorePage", () => {
  it("asks for an event before querying anything", async () => {
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/choose an event to build a chart/i)).toBeInTheDocument();
    expect(fetchExplore).not.toHaveBeenCalled();
  });

  it("writes the picked event to the URL, keeping the period", async () => {
    nav.search = "range=7d";
    renderWithIntl(<ExplorePage />);
    await userEvent.selectOptions(await screen.findByLabelText("Event"), "chat.tool_invoked");
    expect(nav.replace).toHaveBeenCalledWith(
      "/dashboard/analytics/explore?range=7d&event=chat.tool_invoked",
    );
  });

  it("charts an ungrouped query as a line over the period", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({ points: [{ bucket: "2026-07-23", group: null, value: 3 }] });
    renderWithIntl(<ExplorePage />);
    const table = await screen.findByRole("table", { name: /^chat\.tool_invoked,/ });
    expect(within(table).getByRole("row", { name: "Jul 23, 2026 3" })).toBeInTheDocument();
    expect(fetchExplore).toHaveBeenCalledWith(
      "test-token",
      { from: "2026-06-25", to: "2026-07-24", bucket: "day" },
      expect.objectContaining({ event: "chat.tool_invoked" }),
    );
  });

  it("keeps a first bucket that starts before the period", async () => {
    nav.search = "bucket=month&event=chat.tool_invoked&chart=table";
    answer({ points: [{ bucket: "2026-06-01", group: null, value: 5 }] });
    renderWithIntl(<ExplorePage />);
    const table = await screen.findByRole("table", { name: /^chat\.tool_invoked,/ });
    expect(within(table).getByRole("row", { name: /Jun.* 5$/ })).toBeInTheDocument();
  });

  it("shows a no-data state when nothing matched", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({});
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/no matching events/i)).toBeInTheDocument();
  });

  it("ranks actor groups by name when known, else by id", async () => {
    nav.search = "event=chat.tool_invoked&group=actor";
    answer({
      totals: [
        { group: "1", value: 5 },
        { group: "2", value: 2 },
      ],
      actor_names: { "1": "alice" },
    });
    renderWithIntl(<ExplorePage />);
    const table = await screen.findByRole("table", { name: /^chat\.tool_invoked by actor,/i });
    expect(within(table).getByRole("row", { name: "alice 5" })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: "2 2" })).toBeInTheDocument();
  });

  it("shows the totals as a visible table when asked", async () => {
    nav.search = "event=chat.tool_invoked&group=outcome&chart=table";
    answer({ totals: [{ group: null, value: 4 }] });
    renderWithIntl(<ExplorePage />);
    const table = await screen.findByRole("table", { name: /^chat\.tool_invoked by outcome,/ });
    expect(table).not.toHaveClass("sr-only");
    expect(within(table).getByRole("row", { name: "(none) 4" })).toBeInTheDocument();
  });

  it("says when only the top groups are shown", async () => {
    nav.search = "event=chat.tool_invoked&group=tool";
    answer({ totals: [{ group: "search", value: 1 }], truncated: true });
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/top 20/i)).toBeInTheDocument();
  });

  it("renders a stale link with a notice instead of failing", async () => {
    nav.search = "event=gone.event&group=removed";
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/no longer exist/i)).toBeInTheDocument();
    expect(screen.getByText(/choose an event to build a chart/i)).toBeInTheDocument();
    expect(fetchExplore).not.toHaveBeenCalled();
  });

  it("offers an enum field's values from the catalog and adds the filter", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({});
    renderWithIntl(<ExplorePage />);
    await userEvent.selectOptions(await screen.findByLabelText("Field"), "outcome");
    const value = screen.getByLabelText("Value");
    expect(
      within(value)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["ok", "provider_api_error", "null"]);
    await userEvent.selectOptions(value, "provider_api_error");
    await userEvent.click(screen.getByRole("button", { name: "Add filter" }));
    expect(nav.replace).toHaveBeenCalledWith(
      "/dashboard/analytics/explore?event=chat.tool_invoked&filter=outcome%3Aprovider_api_error",
    );
  });

  it("keeps both of two changes made before the URL updates", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({});
    renderWithIntl(<ExplorePage />);
    await userEvent.type(await screen.findByLabelText("Actor ID"), "42");
    // Picking the field blurs the actor box, which writes the actor; the URL never changes here.
    await userEvent.selectOptions(screen.getByLabelText("Field"), "outcome");
    await userEvent.click(screen.getByRole("button", { name: "Add filter" }));
    expect(nav.replace).toHaveBeenLastCalledWith(
      "/dashboard/analytics/explore?event=chat.tool_invoked&actor=42&filter=outcome%3Aok",
    );
  });

  it("keeps a period change made just before a control change", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({});
    renderWithIntl(
      <>
        <PeriodSelector />
        <ExplorePage />
      </>,
    );
    await userEvent.selectOptions(await screen.findByLabelText("Period"), "7d");
    await userEvent.selectOptions(screen.getByLabelText("Measure"), "distinct_actors");
    expect(nav.replace).toHaveBeenLastCalledWith(
      "/dashboard/analytics/explore?range=7d&bucket=day&event=chat.tool_invoked&measure=distinct_actors",
    );
  });

  it("offers only bars and a table for a breakdown, showing a line link as bars", async () => {
    nav.search = "event=chat.tool_invoked&group=tool";
    answer({ totals: [{ group: "search", value: 1 }] });
    renderWithIntl(<ExplorePage />);
    const chart = await screen.findByLabelText("Chart");
    expect(chart).toHaveValue("bar");
    expect(within(chart).queryByRole("option", { name: "Line" })).not.toBeInTheDocument();
  });

  it("shows the access view without user.read", async () => {
    access.userRead = "denied";
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByLabelText("Event")).not.toBeInTheDocument();
  });

  it("only adds a filter value the field accepts", async () => {
    nav.search = "event=chat.tool_invoked";
    answer({});
    renderWithIntl(<ExplorePage />);
    const add = () => screen.getByRole("button", { name: "Add filter" });
    await userEvent.selectOptions(await screen.findByLabelText("Field"), "tool");
    expect(add()).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Field"), "attempts");
    await userEvent.type(screen.getByLabelText("Value"), "two");
    expect(add()).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("Value"));
    await userEvent.type(screen.getByLabelText("Value"), "null");
    expect(add()).toBeEnabled();
    await userEvent.clear(screen.getByLabelText("Value"));
    await userEvent.type(screen.getByLabelText("Value"), "2");
    expect(add()).toBeEnabled();
  });

  it("drops a stale filter value with a notice instead of failing", async () => {
    nav.search = "event=chat.tool_invoked&filter=outcome:removed_reason";
    answer({});
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/no longer exist/i)).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(fetchExplore).toHaveBeenCalledWith(
        "test-token",
        expect.anything(),
        expect.objectContaining({ filters: [] }),
      ),
    );
  });
});
