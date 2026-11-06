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
const plugins = vi.hoisted(() => ({ installed: ["example"] }));
vi.mock("@/lib/plugins/generated", () => ({
  get FRONTEND_PLUGIN_NAMES() {
    return plugins.installed;
  },
}));

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const access = vi.hoisted(() => ({ userRead: "allowed" }));
vi.mock("@/core/permissions/usePermissionCheck", () => ({
  usePermissionCheck: () => access.userRead,
}));
vi.mock("@/lib/analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics")>();
  return { ...actual, listViews: vi.fn() };
});

import { listViews, type AnalyticsView } from "@/lib/analytics";
import {
  AnalyticsNav,
  EXPLORE,
  VIEWS_CHANGED,
  type AnalyticsNavView,
} from "@/core/analytics/components/layout/AnalyticsNav";

const Icon = () => null;
// The rail's views, with Course authoring read from an installable plugin.
const VIEWS: AnalyticsNavView[] = [
  { key: "overview", href: "/dashboard/analytics", icon: Icon },
  { key: "logins", href: "/dashboard/analytics/logins", icon: Icon },
  { key: "authoring", href: "/dashboard/analytics/authoring", icon: Icon, plugin: "example" },
  { key: "explore", href: EXPLORE, icon: Icon },
];

function savedView(id: string, name: string): AnalyticsView {
  return {
    id,
    name,
    config: { filters: [], measure: "count", chart: "line" },
    created_at: "",
    updated_at: "",
  };
}

describe("AnalyticsNav", () => {
  beforeEach(() => {
    nav.pathname = "/dashboard/analytics/logins";
    nav.search = "";
    plugins.installed = ["example"];
    access.userRead = "allowed";
    vi.clearAllMocks();
    vi.mocked(listViews).mockResolvedValue([]);
  });

  it("lists only the views it is given", () => {
    renderWithIntl(
      <AnalyticsNav views={[{ key: "logins", href: "/dashboard/analytics/logins", icon: Icon }]} />,
    );
    expect(screen.getByRole("link", { name: "Logins" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Overview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Explore" })).not.toBeInTheDocument();
  });

  it("is a labelled navigation landmark with a link per view", () => {
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    const rail = screen.getByRole("navigation", { name: "Analytics views" });
    expect(rail).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins",
    );
  });

  it("marks the active view as the current page, including with a trailing slash", () => {
    nav.pathname = "/dashboard/analytics/logins/";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute("aria-current", "page");
  });

  it("marks Overview current only on the analytics index", () => {
    for (const path of ["/dashboard/analytics", "/dashboard/analytics/"]) {
      nav.pathname = path;
      const { unmount } = renderWithIntl(<AnalyticsNav views={VIEWS} />);
      expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(screen.getByRole("link", { name: "Logins" })).not.toHaveAttribute("aria-current");
      unmount();
    }
    nav.pathname = "/dashboard/analytics/logins";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });

  it("links Overview to the analytics index, keeping the period", () => {
    nav.search = "range=7d";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "href",
      "/dashboard/analytics?range=7d",
    );
  });

  it("keeps the selected period when switching views", () => {
    nav.search = "range=7d&bucket=week";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins?range=7d&bucket=week",
    );
  });

  it("links Explore", () => {
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Explore" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/explore",
    );
  });

  it("carries only the period to every view", () => {
    nav.search = "range=7d&bucket=week&event=x&filter=a:b";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    for (const link of screen.getAllByRole("link")) {
      expect(link.getAttribute("href")).toMatch(/\?range=7d&bucket=week$/);
    }
  });

  it("lists a plugin's view while that plugin is installed", () => {
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Course authoring" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/authoring",
    );
  });

  it("hides a plugin's view when that plugin is not installed", () => {
    plugins.installed = [];
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.queryByRole("link", { name: "Course authoring" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logins" })).toBeInTheDocument();
  });

  it("lists saved views under the built-ins, opening Explore with the view and the period", async () => {
    nav.search = "range=7d&event=x";
    vi.mocked(listViews).mockResolvedValue([savedView("v1", "My logins")]);
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    const link = await screen.findByRole("link", { name: "My logins" });
    expect(link).toHaveAttribute("href", "/dashboard/analytics/explore?view=v1&range=7d");
    expect(screen.getByRole("heading", { name: "Saved views" })).toBeInTheDocument();
    expect(listViews).toHaveBeenCalledWith("test-token");
  });

  it("marks the open saved view current instead of Explore", async () => {
    nav.pathname = "/dashboard/analytics/explore";
    nav.search = "view=v1";
    vi.mocked(listViews).mockResolvedValue([savedView("v1", "My logins")]);
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(await screen.findByRole("link", { name: "My logins" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Explore" })).not.toHaveAttribute("aria-current");
  });

  it("reloads the saved views when they change", async () => {
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    await vi.waitFor(() => expect(listViews).toHaveBeenCalledTimes(1));
    vi.mocked(listViews).mockResolvedValue([savedView("v2", "Renamed")]);
    act(() => {
      window.dispatchEvent(new Event(VIEWS_CHANGED));
    });
    expect(await screen.findByRole("link", { name: "Renamed" })).toBeInTheDocument();
  });

  it("hides Explore and saved views without user.read", async () => {
    access.userRead = "denied";
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    expect(screen.getByRole("link", { name: "Logins" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Explore" })).not.toBeInTheDocument();
    await act(async () => {});
    expect(listViews).not.toHaveBeenCalled();
  });

  it("shows no saved-views section when there are none", async () => {
    renderWithIntl(<AnalyticsNav views={VIEWS} />);
    await vi.waitFor(() => expect(listViews).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Saved views" })).not.toBeInTheDocument();
  });
});
