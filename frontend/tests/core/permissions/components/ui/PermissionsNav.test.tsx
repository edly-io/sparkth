import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

const nav = vi.hoisted(() => ({ pathname: "/dashboard/permissions/roles" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

import {
  PermissionsNav,
  type PermissionsTab,
} from "@/core/permissions/components/ui/PermissionsNav";

const TABS: PermissionsTab[] = [
  { key: "roles", href: "/dashboard/permissions/roles" },
  { key: "groups", href: "/dashboard/permissions/groups" },
];

describe("PermissionsNav", () => {
  beforeEach(() => {
    nav.pathname = "/dashboard/permissions/roles";
  });

  it("links to each tab it is given, in order", () => {
    renderWithIntl(<PermissionsNav tabs={TABS} />);

    const links = screen.getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(["Roles", "Groups"]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "/dashboard/permissions/roles",
      "/dashboard/permissions/groups",
    ]);
  });

  it("labels the navigation for screen readers", () => {
    renderWithIntl(<PermissionsNav tabs={TABS} />);

    expect(screen.getByRole("navigation", { name: "Access sections" })).toBeInTheDocument();
  });

  it("marks only the open tab as the current page", () => {
    nav.pathname = "/dashboard/permissions/groups";
    renderWithIntl(<PermissionsNav tabs={TABS} />);

    expect(screen.getByRole("link", { name: "Groups" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Roles" })).not.toHaveAttribute("aria-current");
  });

  it("marks the open tab when the path has a trailing slash", () => {
    nav.pathname = "/dashboard/permissions/groups/";
    renderWithIntl(<PermissionsNav tabs={TABS} />);

    expect(screen.getByRole("link", { name: "Groups" })).toHaveAttribute("aria-current", "page");
  });

  it("marks no tab when the path is outside every tab", () => {
    nav.pathname = "/dashboard/permissions/rolesets";
    renderWithIntl(<PermissionsNav tabs={TABS} />);

    for (const link of screen.getAllByRole("link")) {
      expect(link).not.toHaveAttribute("aria-current");
    }
  });
});
