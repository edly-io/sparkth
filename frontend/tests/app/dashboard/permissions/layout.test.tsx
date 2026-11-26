import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const nav = vi.hoisted(() => ({ pathname: "/dashboard/permissions/roles" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));
const checkPermissions = vi.hoisted(() => vi.fn());
vi.mock("@/core/permissions/client", () => ({ checkPermissions }));

import PermissionsLayout from "@/app/dashboard/permissions/layout";

beforeEach(() => {
  vi.clearAllMocks();
  nav.pathname = "/dashboard/permissions/roles";
  vi.spyOn(console, "error").mockImplementation(() => {});
});

function renderLayout() {
  renderWithIntl(
    <PermissionsLayout>
      <p>tab body</p>
    </PermissionsLayout>,
  );
}

describe("PermissionsLayout", () => {
  it("asks for permission.read, role.read and group.read in one request", async () => {
    checkPermissions.mockResolvedValue([true, true, true]);
    renderLayout();

    await screen.findByText("tab body");
    expect(checkPermissions).toHaveBeenCalledTimes(1);
    expect(checkPermissions).toHaveBeenCalledWith("test-token", [
      { permission: "permission.read", scope: "global" },
      { permission: "role.read", scope: "role" },
      { permission: "group.read", scope: "group" },
    ]);
  });

  it("shows the tabs and the open tab when all three are granted", async () => {
    checkPermissions.mockResolvedValue([true, true, true]);
    renderLayout();

    expect(await screen.findByText("tab body")).toBeInTheDocument();
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
  });

  it("leaves the section heading and tabs to a page below a tab, such as one role's", async () => {
    nav.pathname = "/dashboard/permissions/roles/role";
    checkPermissions.mockResolvedValue([true, true, true]);
    renderLayout();

    expect(await screen.findByText("tab body")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Access & permissions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Access sections" })).not.toBeInTheDocument();
  });

  it.each([
    ["permission.read", [false, true, true]],
    ["role.read", [true, false, true]],
    ["group.read", [true, true, false]],
  ])("refuses access without %s", async (_missing, answers) => {
    checkPermissions.mockResolvedValue(answers);
    renderLayout();

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Access sections" })).not.toBeInTheDocument();
  });

  it("refuses access when the check fails", async () => {
    checkPermissions.mockRejectedValue(new Error("network down"));
    renderLayout();

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
  });

  it("shows the heading but neither tabs nor content while checking", () => {
    checkPermissions.mockReturnValue(new Promise(() => {}));
    renderLayout();

    expect(
      screen.getByRole("heading", { level: 1, name: "Access & permissions" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Access sections" })).not.toBeInTheDocument();
  });
});
