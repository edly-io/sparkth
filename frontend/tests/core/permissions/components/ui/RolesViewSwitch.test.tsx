import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { RolesViewSwitch } from "@/core/permissions/components/ui/RolesViewSwitch";

describe("RolesViewSwitch", () => {
  it("marks List as the current view and links to Compare", () => {
    renderWithIntl(<RolesViewSwitch current="list" />);

    const views = screen.getByRole("group", { name: "View" });
    const list = within(views).getByRole("link", { name: "List" });
    expect(list).toHaveAttribute("href", "/dashboard/permissions/roles");
    expect(list).toHaveAttribute("aria-current", "page");
    const compare = within(views).getByRole("link", { name: "Compare permissions" });
    expect(compare).toHaveAttribute("href", "/dashboard/permissions/roles/compare");
    expect(compare).not.toHaveAttribute("aria-current");
  });

  it("marks Compare as the current view and links back to List", () => {
    renderWithIntl(<RolesViewSwitch current="compare" />);

    const views = screen.getByRole("group", { name: "View" });
    const compare = within(views).getByRole("link", { name: "Compare permissions" });
    expect(compare).toHaveAttribute("href", "/dashboard/permissions/roles/compare");
    expect(compare).toHaveAttribute("aria-current", "page");
    const list = within(views).getByRole("link", { name: "List" });
    expect(list).toHaveAttribute("href", "/dashboard/permissions/roles");
    expect(list).not.toHaveAttribute("aria-current");
  });
});
