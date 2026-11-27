import { describe, it, expect } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { RolePermissionList } from "@/core/permissions/components/ui/RolePermissionList";
import type { PermissionResponse } from "@/core/permissions/types";

function permission(
  name: string,
  label: string,
  category: string,
  risks: PermissionResponse["risks"] = [],
): PermissionResponse {
  return { name, label, description: `${label}, in a sentence.`, category, risks, requires: [] };
}

const PERMISSIONS = [
  permission("role.read", "See roles", "Users & access"),
  permission("role.update", "Edit roles", "Users & access", ["delegates_access"]),
  permission("compose.conversation.read", "Read conversations", "Compose"),
];

function renderList(granted: string[] = ["role.read", "compose.conversation.read"]) {
  renderWithIntl(<RolePermissionList permissions={PERMISSIONS} granted={new Set(granted)} />);
}

describe("RolePermissionList", () => {
  it("says how many permissions the role grants", () => {
    renderList();

    expect(screen.getByText(/of 3 permissions granted/)).toHaveTextContent(
      "2 of 3 permissions granted",
    );
  });

  it("groups the permissions under their category, each group counting what it grants", () => {
    renderList();

    const access = screen.getByRole("group", { name: "Users & access" });
    expect(within(access).getByText("1 of 2")).toBeInTheDocument();
    expect(within(access).getByRole("checkbox", { name: "See roles" })).toBeInTheDocument();
    expect(within(access).getByRole("checkbox", { name: "Edit roles" })).toBeInTheDocument();
    const compose = screen.getByRole("group", { name: "Compose" });
    expect(within(compose).getByText("1 of 1")).toBeInTheDocument();
  });

  it("shows each permission's description, internal name and risks", () => {
    renderList();

    expect(screen.getByText("Edit roles, in a sentence.")).toBeInTheDocument();
    expect(screen.getByText("role.update")).toBeInTheDocument();
    expect(screen.getByText("Can give others access")).toBeInTheDocument();
  });

  it("ticks the permissions the role grants, and none can be changed", () => {
    renderList();

    expect(screen.getByRole("checkbox", { name: "See roles" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).not.toBeChecked();
    for (const checkbox of screen.getAllByRole("checkbox")) expect(checkbox).toBeDisabled();
  });

  it("collapses a group and expands it again", async () => {
    renderList();

    const toggle = screen.getByRole("button", { name: /Users & access/ });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("checkbox", { name: "See roles" })).not.toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.getByRole("checkbox", { name: "See roles" })).toBeInTheDocument();
  });

  it("filters by label, category or internal name", async () => {
    renderList();
    const filter = screen.getByLabelText("Filter permissions");

    await userEvent.type(filter, "edit");
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "See roles" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Compose" })).not.toBeInTheDocument();

    await userEvent.clear(filter);
    await userEvent.type(filter, "compose.conversation");
    expect(screen.getByRole("checkbox", { name: "Read conversations" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Users & access" })).not.toBeInTheDocument();
  });

  it("says so when nothing matches the filter", async () => {
    renderList();

    await userEvent.type(screen.getByLabelText("Filter permissions"), "nothing like this");

    expect(screen.getByText("No permissions match.")).toBeInTheDocument();
  });
});
