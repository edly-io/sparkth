import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const client = vi.hoisted(() => ({ listRoles: vi.fn(), listPermissions: vi.fn() }));
vi.mock("@/core/permissions/client", () => client);
const { listRoles, listPermissions } = client;

import ComparePage from "@/app/dashboard/permissions/(tabs)/roles/compare/ComparePage";

function permission(name: string, label: string, category: string): PermissionResponse {
  return { name, label, description: `${label}.`, category, risks: [], requires: [] };
}

const ROLE: RoleResponse = {
  id: 1,
  name: "admin",
  description: null,
  permissions: ["role.read"],
  is_builtin: true,
  is_default: false,
  user_count: 0,
  group_count: 0,
  risks: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  listRoles.mockResolvedValue([ROLE]);
  listPermissions.mockResolvedValue([
    permission("role.read", "See roles", "Users & access"),
    permission("role.update", "Edit roles", "Users & access"),
    permission("compose.conversation.read", "Read conversations", "Compose"),
  ]);
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("ComparePage", () => {
  it("opens on the Compare view and says it is view only", async () => {
    renderWithIntl(<ComparePage />);

    expect(screen.getByRole("link", { name: "Compare permissions" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("View only")).toBeInTheDocument();
    await screen.findAllByRole("table");
  });

  it("compares the roles one category at a time", async () => {
    renderWithIntl(<ComparePage />);

    const access = await screen.findByRole("table", { name: "Users & access" });
    expect(within(access).getByRole("row", { name: /See roles/ })).toHaveTextContent("Granted");
    expect(within(access).getByRole("row", { name: /Edit roles/ })).toHaveTextContent(
      "Not granted",
    );
    expect(screen.getByRole("heading", { level: 2, name: "Users & access" })).toBeInTheDocument();
    const compose = screen.getByRole("table", { name: "Compose" });
    expect(within(compose).getByRole("row", { name: /Read conversations/ })).toBeInTheDocument();
    expect(listRoles).toHaveBeenCalledWith("test-token");
    expect(listPermissions).toHaveBeenCalledWith("test-token");
  });

  it("explains the marks and that roles are changed on their own pages", async () => {
    renderWithIntl(<ComparePage />);

    await screen.findAllByRole("table");
    const legend = screen.getByRole("list", { name: "Legend" });
    expect(within(legend).getByText("Granted")).toBeInTheDocument();
    expect(within(legend).getByText("Not granted")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This page is for comparing only. To change what a role can do, click its name to open the role.",
      ),
    ).toBeInTheDocument();
  });

  it("says there are no permissions when there are none to compare", async () => {
    listPermissions.mockResolvedValue([]);
    renderWithIntl(<ComparePage />);

    expect(await screen.findByText("No permissions to compare.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("says there are no roles when there are none to compare", async () => {
    listRoles.mockResolvedValue([]);
    renderWithIntl(<ComparePage />);

    expect(await screen.findByText("No roles yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows a spinner while the roles and permissions load", () => {
    listRoles.mockReturnValue(new Promise(() => {}));
    renderWithIntl(<ComparePage />);

    expect(screen.getByRole("status", { name: "Loading the comparison…" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Legend" })).not.toBeInTheDocument();
  });

  it.each([
    ["roles", () => listRoles.mockRejectedValue(new Error("network down"))],
    ["permissions", () => listPermissions.mockRejectedValue(new Error("network down"))],
  ])("says so when the %s can't be loaded", async (_, fail) => {
    fail();
    renderWithIntl(<ComparePage />);

    expect(
      await screen.findByText("Couldn't load the comparison. Try again later."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
