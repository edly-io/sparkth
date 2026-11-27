import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { PermissionPicker } from "@/core/permissions/components/ui/PermissionPicker";
import type { PermissionResponse } from "@/core/permissions/types";

function permission(
  name: string,
  label: string,
  category: string,
  risks: PermissionResponse["risks"] = [],
): PermissionResponse {
  return { name, label, description: `${label}.`, category, risks, requires: [] };
}

const PERMISSIONS = [
  permission("role.read", "See roles", "Users & access"),
  permission("role.update", "Change roles", "Users & access", ["delegates_access"]),
  permission("compose.conversation.read", "Read conversations", "Compose"),
];

function renderPicker(chosen: string[] = [], onToggle = vi.fn()) {
  renderWithIntl(
    <PermissionPicker permissions={PERMISSIONS} chosen={new Set(chosen)} onToggle={onToggle} />,
  );
  return { onToggle };
}

describe("PermissionPicker", () => {
  it("lists every permission by its label under its category", () => {
    renderPicker();

    const access = screen.getByRole("group", { name: "Users & access" });
    expect(within(access).getByRole("checkbox", { name: "See roles" })).toBeInTheDocument();
    expect(within(access).getByRole("checkbox", { name: "Change roles" })).toBeInTheDocument();
    const compose = screen.getByRole("group", { name: "Compose" });
    expect(
      within(compose).getByRole("checkbox", { name: "Read conversations" }),
    ).toBeInTheDocument();
  });

  it("tags a permission with its risks", () => {
    renderPicker();

    const access = screen.getByRole("group", { name: "Users & access" });
    expect(within(access).getByText("Can give others access")).toBeInTheDocument();
  });

  it("checks the chosen permissions and says how many are chosen", () => {
    renderPicker(["role.read", "compose.conversation.read"]);

    expect(screen.getByRole("checkbox", { name: "See roles" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Change roles" })).not.toBeChecked();
    expect(screen.getByText("2 chosen")).toBeInTheDocument();
  });

  it("hands over the permission checked or unchecked", async () => {
    const { onToggle } = renderPicker(["role.read"]);

    await userEvent.click(screen.getByRole("checkbox", { name: "Change roles" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "See roles" }));

    expect(onToggle.mock.calls).toEqual([["role.update"], ["role.read"]]);
  });

  it("filters by label, category or internal name as you search", async () => {
    renderPicker();

    await userEvent.type(screen.getByLabelText("Search permissions"), "change");
    expect(screen.getByRole("checkbox", { name: "Change roles" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "See roles" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Compose" })).not.toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Search permissions"));
    await userEvent.type(screen.getByLabelText("Search permissions"), "compose");
    expect(screen.getByRole("checkbox", { name: "Read conversations" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Users & access" })).not.toBeInTheDocument();

    await userEvent.clear(screen.getByLabelText("Search permissions"));
    await userEvent.type(screen.getByLabelText("Search permissions"), "role.update");
    expect(screen.getByRole("checkbox", { name: "Change roles" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "See roles" })).not.toBeInTheDocument();
  });

  it("keeps a chosen permission chosen while the search hides it", async () => {
    renderPicker(["role.read"]);

    await userEvent.type(screen.getByLabelText("Search permissions"), "compose");

    expect(screen.getByText("1 chosen")).toBeInTheDocument();
  });

  it("says so when nothing matches the search", async () => {
    renderPicker();

    await userEvent.type(screen.getByLabelText("Search permissions"), "nothing like this");

    expect(screen.getByText("No permissions match.")).toBeInTheDocument();
  });
});
