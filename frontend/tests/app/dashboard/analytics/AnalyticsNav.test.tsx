import { beforeEach, describe, it, expect, vi } from "vitest";
import { act, screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl-test-utils";

const nav = vi.hoisted(() => ({ pathname: "/dashboard/analytics/logins", search: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useSearchParams: () => new URLSearchParams(nav.search),
}));

// The plugins installed in the backend build. No PluginProvider is mounted: analytics must not
// depend on the viewer's own plugin switches.
const plugins = vi.hoisted(() => ({ installed: ["chat"] }));
vi.mock("@/lib/plugins/generated", () => ({
  get FRONTEND_PLUGIN_NAMES() {
    return plugins.installed;
  },
}));

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ token: "test-token" }) }));
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, listViews: vi.fn() };
});

import { listViews, type AnalyticsView } from "@/lib/analytics";
import { AnalyticsNav, VIEWS_CHANGED } from "@/app/dashboard/analytics/AnalyticsNav";

function savedView(id: string, name: string): AnalyticsView {
  return { id, name, config: {}, created_at: "", updated_at: "" };
}

describe("AnalyticsNav", () => {
  beforeEach(() => {
    nav.pathname = "/dashboard/analytics/logins";
    nav.search = "";
    plugins.installed = ["chat"];
    vi.clearAllMocks();
    vi.mocked(listViews).mockResolvedValue([]);
  });

  it("is a labelled navigation landmark with a link per view", () => {
    renderWithIntl(<AnalyticsNav />);
    const rail = screen.getByRole("navigation", { name: "Analytics views" });
    expect(rail).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins",
    );
  });

  it("marks the active view as the current page, including with a trailing slash", () => {
    nav.pathname = "/dashboard/analytics/logins/";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute("aria-current", "page");
  });

  it("marks Overview current only on the analytics index", () => {
    for (const path of ["/dashboard/analytics", "/dashboard/analytics/"]) {
      nav.pathname = path;
      const { unmount } = renderWithIntl(<AnalyticsNav />);
      expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(screen.getByRole("link", { name: "Logins" })).not.toHaveAttribute("aria-current");
      unmount();
    }
    nav.pathname = "/dashboard/analytics/logins";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });

  it("links Overview to the analytics index, keeping the period", () => {
    nav.search = "range=7d";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "href",
      "/dashboard/analytics?range=7d",
    );
  });

  it("keeps the selected period when switching views", () => {
    nav.search = "range=7d&bucket=week";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins?range=7d&bucket=week",
    );
  });

  it("links Explore", () => {
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Explore" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/explore",
    );
  });

  it("carries only the period to every view", () => {
    nav.search = "range=7d&bucket=week&event=x&filter=a:b";
    renderWithIntl(<AnalyticsNav />);
    for (const link of screen.getAllByRole("link")) {
      expect(link.getAttribute("href")).toMatch(/\?range=7d&bucket=week$/);
    }
  });

  it("lists Course authoring while chat is installed", () => {
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Course authoring" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/authoring",
    );
  });

  it("hides Course authoring when chat is not installed", () => {
    plugins.installed = [];
    renderWithIntl(<AnalyticsNav />);
    expect(screen.queryByRole("link", { name: "Course authoring" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logins" })).toBeInTheDocument();
  });

  it("lists saved views under the built-ins, opening Explore with the view and the period", async () => {
    nav.search = "range=7d&event=x";
    vi.mocked(listViews).mockResolvedValue([savedView("v1", "My logins")]);
    renderWithIntl(<AnalyticsNav />);
    const link = await screen.findByRole("link", { name: "My logins" });
    expect(link).toHaveAttribute("href", "/dashboard/analytics/explore?view=v1&range=7d");
    expect(screen.getByRole("heading", { name: "Saved views" })).toBeInTheDocument();
    expect(listViews).toHaveBeenCalledWith("test-token");
  });

  it("marks the open saved view current instead of Explore", async () => {
    nav.pathname = "/dashboard/analytics/explore";
    nav.search = "view=v1";
    vi.mocked(listViews).mockResolvedValue([savedView("v1", "My logins")]);
    renderWithIntl(<AnalyticsNav />);
    expect(await screen.findByRole("link", { name: "My logins" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Explore" })).not.toHaveAttribute("aria-current");
  });

  it("reloads the saved views when they change", async () => {
    renderWithIntl(<AnalyticsNav />);
    await vi.waitFor(() => expect(listViews).toHaveBeenCalledTimes(1));
    vi.mocked(listViews).mockResolvedValue([savedView("v2", "Renamed")]);
    act(() => {
      window.dispatchEvent(new Event(VIEWS_CHANGED));
    });
    expect(await screen.findByRole("link", { name: "Renamed" })).toBeInTheDocument();
  });

  it("shows no saved-views section when there are none", async () => {
    renderWithIntl(<AnalyticsNav />);
    await vi.waitFor(() => expect(listViews).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Saved views" })).not.toBeInTheDocument();
  });
});
