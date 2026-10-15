import { beforeEach, describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl-test-utils";

const nav = vi.hoisted(() => ({ pathname: "/dashboard/analytics/logins", search: "" }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useSearchParams: () => new URLSearchParams(nav.search),
}));

// The viewer's enabled plugins, as the dashboard's PluginProvider reports them.
const plugins = vi.hoisted(() => ({ enabled: new Set(["chat"]) }));
vi.mock("@/lib/plugins/context", () => ({
  usePluginContext: () => ({ isPluginEnabled: (name: string) => plugins.enabled.has(name) }),
}));

import { AnalyticsNav } from "@/app/dashboard/analytics/AnalyticsNav";

describe("AnalyticsNav", () => {
  beforeEach(() => {
    nav.pathname = "/dashboard/analytics/logins";
    nav.search = "";
    plugins.enabled = new Set(["chat"]);
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

  it("marks nothing current on an unrelated path", () => {
    nav.pathname = "/dashboard/analytics";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Logins" })).not.toHaveAttribute("aria-current");
  });

  it("keeps the selected period when switching views", () => {
    nav.search = "range=7d&bucket=week";
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Logins" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/logins?range=7d&bucket=week",
    );
  });

  it("shows Course authoring when the chat plugin is enabled", () => {
    renderWithIntl(<AnalyticsNav />);
    expect(screen.getByRole("link", { name: "Course authoring" })).toHaveAttribute(
      "href",
      "/dashboard/analytics/authoring",
    );
  });

  it("hides Course authoring when the viewer has the chat plugin disabled", () => {
    plugins.enabled = new Set();
    renderWithIntl(<AnalyticsNav />);
    expect(screen.queryByRole("link", { name: "Course authoring" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Logins" })).toBeInTheDocument();
  });
});
