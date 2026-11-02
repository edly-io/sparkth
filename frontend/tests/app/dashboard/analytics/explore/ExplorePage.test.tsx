import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import { renderWithIntl } from "@/tests/intl-test-utils";
import en from "@/messages/en.json";

vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Analytics data access: keep the real helpers, stub the fetches.
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return {
    ...actual,
    fetchEventCatalog: vi.fn(),
    fetchExplore: vi.fn(),
    fetchView: vi.fn(),
    createView: vi.fn(),
    updateView: vi.fn(),
    deleteView: vi.fn(),
  };
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
  createView,
  deleteView,
  fetchEventCatalog,
  fetchExplore,
  fetchView,
  updateView,
  type AnalyticsView,
  type EventCatalogEntry,
  type ExploreResult,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
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

function savedView(
  config: Partial<AnalyticsView["config"]>,
  id = "v1",
  name = "Logins",
): AnalyticsView {
  const full: AnalyticsView["config"] = { filters: [], measure: "count", chart: "line", ...config };
  return { id, name, config: full, created_at: "", updated_at: "" };
}

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

  it("opens a saved view by applying its config to the URL, keeping the period", async () => {
    nav.search = "range=7d&view=v1";
    vi.mocked(fetchView).mockResolvedValue(savedView({ event: "auth.login", chart: "bar" }));
    renderWithIntl(<ExplorePage />);
    await vi.waitFor(() =>
      expect(nav.replace).toHaveBeenCalledWith(
        "/dashboard/analytics/explore?range=7d&view=v1&event=auth.login&chart=bar",
      ),
    );
    expect(fetchView).toHaveBeenCalledWith("test-token", "v1");
  });

  it("keeps unsaved edits in the URL when a saved view's link is reloaded", async () => {
    nav.search = "view=v1&event=chat.tool_invoked";
    answer({});
    vi.mocked(fetchView).mockResolvedValue(savedView({ event: "auth.login", chart: "bar" }));
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByRole("heading", { name: "Logins" })).toBeInTheDocument();
    expect(nav.replace).not.toHaveBeenCalled();
  });

  it("shows the notice for a saved view naming a removed field", async () => {
    nav.search = "view=v1";
    vi.mocked(fetchView).mockResolvedValue(
      savedView({ event: "chat.tool_invoked", filters: [{ field: "gone", value: "x" }] }),
    );
    const first = renderWithIntl(<ExplorePage />);
    await vi.waitFor(() => expect(nav.replace).toHaveBeenCalled());
    first.unmount();
    // What the router would render next.
    nav.search = vi.mocked(nav.replace).mock.calls[0][0].split("?")[1];
    answer({});
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/no longer exist/i)).toBeInTheDocument();
  });

  it.each([
    ["an unknown id (404)", "9b2f6c1e-4d1a-4c3b-8e2f-0a1b2c3d4e5f", 404],
    ["an id that isn't a UUID (422)", "abc", 422],
  ])("says when a saved view can't be found: %s", async (_, id, status) => {
    nav.search = `view=${id}`;
    vi.mocked(fetchView).mockRejectedValue(
      new ApiRequestError({ message: "Not found", fieldErrors: {} }, status),
    );
    renderWithIntl(<ExplorePage />);
    expect(await screen.findByText(/saved view doesn't exist/i)).toBeInTheDocument();
  });

  it("saves the config as a new view and opens it", async () => {
    nav.search = "range=7d&event=auth.login";
    vi.mocked(createView).mockResolvedValue(savedView({ event: "auth.login" }, "v9"));
    renderWithIntl(<ExplorePage />);
    await userEvent.click(await screen.findByRole("button", { name: "Save view" }));
    await userEvent.type(screen.getByLabelText("Name"), "Logins");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(createView).toHaveBeenCalledWith(
      "test-token",
      "Logins",
      expect.objectContaining({ event: "auth.login" }),
    );
    await vi.waitFor(() =>
      expect(nav.replace).toHaveBeenLastCalledWith(
        "/dashboard/analytics/explore?range=7d&view=v9&event=auth.login",
      ),
    );
  });

  it("doesn't fetch a view it just saved once the URL opens it", async () => {
    nav.search = "range=7d&event=auth.login";
    answer({});
    vi.mocked(createView).mockResolvedValue(savedView({ event: "auth.login" }, "v9"));
    const { rerender } = renderWithIntl(<ExplorePage />);
    await userEvent.click(await screen.findByRole("button", { name: "Save view" }));
    await userEvent.type(screen.getByLabelText("Name"), "Logins");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(nav.replace).toHaveBeenCalled());
    nav.search = "range=7d&view=v9&event=auth.login";
    rerender(
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
        <ExplorePage />
      </NextIntlClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Logins" })).toBeInTheDocument();
    expect(fetchView).not.toHaveBeenCalled();
  });

  it("says when the name is taken", async () => {
    nav.search = "event=auth.login";
    vi.mocked(createView).mockRejectedValue(
      new ApiRequestError({ message: "exists", fieldErrors: {} }, 409),
    );
    renderWithIntl(<ExplorePage />);
    await userEvent.click(await screen.findByRole("button", { name: "Save view" }));
    await userEvent.type(screen.getByLabelText("Name"), "Logins");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/already have a view with this name/i)).toBeInTheDocument();
  });

  describe("with a saved view open", () => {
    beforeEach(() => {
      nav.search = "view=v1&event=auth.login";
      vi.mocked(fetchView).mockResolvedValue(savedView({ event: "auth.login" }));
      answer({});
    });

    it("saves the current config to the open view", async () => {
      vi.mocked(updateView).mockResolvedValue(savedView({ event: "auth.login" }));
      renderWithIntl(<ExplorePage />);
      await userEvent.click(await screen.findByRole("button", { name: "Save" }));
      expect(updateView).toHaveBeenCalledWith("test-token", "v1", {
        config: expect.objectContaining({ event: "auth.login" }),
      });
    });

    it("re-applies the view's config when the URL drops it", async () => {
      const page = renderWithIntl(<ExplorePage />);
      await screen.findByRole("button", { name: "Save" });
      nav.replace.mockClear();
      // The rail's link for the open view carries only the view and period.
      nav.search = "view=v1&range=7d";
      page.rerender(
        <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
          <ExplorePage />
        </NextIntlClientProvider>,
      );
      await vi.waitFor(() =>
        expect(nav.replace).toHaveBeenCalledWith(
          "/dashboard/analytics/explore?range=7d&view=v1&event=auth.login",
        ),
      );
    });

    it("saves as a new view", async () => {
      vi.mocked(createView).mockResolvedValue(savedView({ event: "auth.login" }, "v2", "Copy"));
      renderWithIntl(<ExplorePage />);
      await userEvent.click(await screen.findByRole("button", { name: "Save as new" }));
      await userEvent.type(screen.getByLabelText("Name"), "Copy");
      await userEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(createView).toHaveBeenCalledWith(
        "test-token",
        "Copy",
        expect.objectContaining({ event: "auth.login" }),
      );
    });

    it("renames the view", async () => {
      vi.mocked(updateView).mockResolvedValue(savedView({ event: "auth.login" }, "v1", "Renamed"));
      renderWithIntl(<ExplorePage />);
      await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
      const name = screen.getByLabelText("Name");
      expect(name).toHaveValue("Logins");
      await userEvent.clear(name);
      await userEvent.type(name, "Renamed");
      await userEvent.click(screen.getByRole("button", { name: "Save" }));
      expect(updateView).toHaveBeenCalledWith("test-token", "v1", { name: "Renamed" });
    });

    it("deletes the view and keeps the config", async () => {
      vi.spyOn(window, "confirm").mockReturnValue(true);
      vi.mocked(deleteView).mockResolvedValue();
      renderWithIntl(<ExplorePage />);
      await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
      expect(deleteView).toHaveBeenCalledWith("test-token", "v1");
      await vi.waitFor(() =>
        expect(nav.replace).toHaveBeenLastCalledWith(
          "/dashboard/analytics/explore?event=auth.login",
        ),
      );
    });
  });
});
