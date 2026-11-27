import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard/permissions/roles" }));

import TabsLayout from "@/app/dashboard/permissions/(tabs)/layout";

describe("TabsLayout", () => {
  it("shows the section heading and its tabs above the open tab", () => {
    renderWithIntl(
      <TabsLayout>
        <p>tab body</p>
      </TabsLayout>,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "Access & permissions" }),
    ).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Access sections" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Roles" })).toHaveAttribute(
      "href",
      "/dashboard/permissions/roles",
    );
    expect(screen.getByRole("link", { name: "Groups" })).toHaveAttribute(
      "href",
      "/dashboard/permissions/groups",
    );
    expect(screen.getByText("tab body")).toBeInTheDocument();
  });
});
