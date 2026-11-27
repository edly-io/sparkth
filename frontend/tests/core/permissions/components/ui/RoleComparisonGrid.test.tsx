import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { RoleComparisonGrid } from "@/core/permissions/components/ui/RoleComparisonGrid";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

function permission(
  name: string,
  label: string,
  risks: PermissionResponse["risks"] = [],
): PermissionResponse {
  return {
    name,
    label,
    description: `${label}.`,
    category: "Users & access",
    risks,
    requires: [],
  };
}

function role(id: number, name: string, permissions: string[], isBuiltin = false): RoleResponse {
  return {
    id,
    name,
    description: null,
    permissions,
    is_builtin: isBuiltin,
    is_default: false,
    user_count: 0,
    group_count: 0,
    risks: [],
  };
}

const PERMISSIONS = [
  permission("role.read", "See roles"),
  permission("role.update", "Edit roles", ["delegates_access"]),
  permission("role.delete", "Delete roles"),
];
const ROLES = [
  role(1, "admin", ["role.read", "role.update"], true),
  role(2, "course_author", ["role.read"]),
];

function renderGrid() {
  renderWithIntl(
    <RoleComparisonGrid caption="Users & access" permissions={PERMISSIONS} roles={ROLES} />,
  );
}

describe("RoleComparisonGrid", () => {
  it("is a table named by its caption", () => {
    renderGrid();

    expect(screen.getByRole("table", { name: "Users & access" })).toBeInTheDocument();
  });

  it("heads a column with each role, linking to its page and saying what kind it is", () => {
    renderGrid();

    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((header) => within(header).queryByRole("link")?.textContent)).toEqual([
      undefined,
      "Admin",
      "Course author",
    ]);
    expect(within(headers[1]).getByRole("link")).toHaveAttribute(
      "href",
      "/dashboard/permissions/roles/role?id=1",
    );
    expect(within(headers[1]).getByText("Built-in")).toBeInTheDocument();
    expect(within(headers[2]).getByText("Custom")).toBeInTheDocument();
  });

  it("leaves out that a role is automatic", () => {
    renderWithIntl(
      <RoleComparisonGrid
        caption="Users & access"
        permissions={PERMISSIONS}
        roles={[{ ...ROLES[0], is_default: true }]}
      />,
    );

    expect(screen.getByText("Built-in")).toBeInTheDocument();
    expect(screen.queryByText("Automatic")).not.toBeInTheDocument();
  });

  it("names each permission's row by its label alone", () => {
    renderGrid();

    expect(screen.getByRole("rowheader", { name: "Edit roles" })).toBeInTheDocument();
  });

  it("gives each permission a row with its label, internal name and risks", () => {
    renderGrid();

    const row = screen.getByRole("row", { name: /Edit roles/ });
    const header = within(row).getByRole("rowheader");
    expect(within(header).getByText("role.update")).toBeInTheDocument();
    expect(within(header).getByText("Can give others access")).toBeInTheDocument();
  });

  it("says for each role whether it is granted the permission", () => {
    renderGrid();

    const row = screen.getByRole("row", { name: /Edit roles/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["Granted", "Not granted"]);
  });

  it("marks a permission no role has", () => {
    renderGrid();

    expect(
      within(screen.getByRole("row", { name: /Delete roles/ })).getByText("No role has this yet"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("row", { name: /See roles/ })).queryByText("No role has this yet"),
    ).not.toBeInTheDocument();
  });
});
