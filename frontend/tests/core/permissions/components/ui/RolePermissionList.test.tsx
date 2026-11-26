import { describe, it, expect, vi } from "vitest";
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

  it("hands over the permissions granted once one is ticked or unticked", async () => {
    const onChange = vi.fn();
    renderWithIntl(
      <RolePermissionList
        permissions={PERMISSIONS}
        granted={new Set(["role.read"])}
        onChange={onChange}
      />,
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "Edit roles" }));
    expect(onChange).toHaveBeenLastCalledWith(new Set(["role.read", "role.update"]));
    await userEvent.click(screen.getByRole("checkbox", { name: "See roles" }));
    expect(onChange).toHaveBeenLastCalledWith(new Set());
  });

  it("grants every permission in a category when some are granted", async () => {
    const onChange = vi.fn();
    renderWithIntl(
      <RolePermissionList
        permissions={PERMISSIONS}
        granted={new Set(["role.read", "compose.conversation.read"])}
        onChange={onChange}
      />,
    );

    const all = screen.getByRole("checkbox", { name: "All permissions in Users & access" });
    expect(all).not.toBeChecked();
    expect(all).toHaveProperty("indeterminate", true);
    await userEvent.click(all);

    expect(onChange).toHaveBeenLastCalledWith(
      new Set(["role.read", "compose.conversation.read", "role.update"]),
    );
  });

  it("clears every permission in a category when all are granted", async () => {
    const onChange = vi.fn();
    renderWithIntl(
      <RolePermissionList
        permissions={PERMISSIONS}
        granted={new Set(["role.read", "role.update", "compose.conversation.read"])}
        onChange={onChange}
      />,
    );

    const all = screen.getByRole("checkbox", { name: "All permissions in Users & access" });
    expect(all).toBeChecked();
    await userEvent.click(all);

    expect(onChange).toHaveBeenLastCalledWith(new Set(["compose.conversation.read"]));
  });

  it("grants the whole category, including permissions the filter hides", async () => {
    const onChange = vi.fn();
    renderWithIntl(
      <RolePermissionList permissions={PERMISSIONS} granted={new Set()} onChange={onChange} />,
    );

    await userEvent.type(screen.getByLabelText("Filter permissions"), "edit");
    await userEvent.click(
      screen.getByRole("checkbox", { name: "All permissions in Users & access" }),
    );

    expect(onChange).toHaveBeenLastCalledWith(new Set(["role.read", "role.update"]));
  });

  it("can't change a whole category when the role can't be changed", () => {
    renderList();

    expect(
      screen.getByRole("checkbox", { name: "All permissions in Users & access" }),
    ).toBeDisabled();
  });

  it("shows the actions it is given beside the filter", () => {
    renderWithIntl(
      <RolePermissionList
        permissions={PERMISSIONS}
        granted={new Set()}
        actions={<button type="button">Save</button>}
      />,
    );

    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
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
