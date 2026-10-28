import { beforeEach, describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
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

import { AnalyticsNav } from "@/app/dashboard/analytics/AnalyticsNav";

describe("AnalyticsNav", () => {
  beforeEach(() => {
    nav.pathname = "/dashboard/analytics/logins";
    nav.search = "";
    plugins.installed = ["chat"];
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
});
