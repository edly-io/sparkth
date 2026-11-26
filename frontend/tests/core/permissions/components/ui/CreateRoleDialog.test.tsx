import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const client = vi.hoisted(() => ({ listPermissions: vi.fn() }));
vi.mock("@/core/permissions/client", () => client);
const { listPermissions } = client;

import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";

function permission(name: string, label: string): PermissionResponse {
  return {
    name,
    label,
    description: `${label}.`,
    category: "Users & access",
    risks: [],
    requires: [],
  };
}

function role(id: number, name: string, permissions: string[]): RoleResponse {
  return {
    id,
    name,
    description: null,
    permissions,
    is_builtin: false,
    is_default: false,
    user_count: 0,
    group_count: 0,
    risks: [],
  };
}

const PERMISSIONS = [
  permission("role.read", "See roles"),
  permission("role.update", "Change roles"),
  permission("group.read", "See groups"),
];
const ROLES = [
  role(1, "sparkth_user", ["group.read"]),
  role(2, "Course author", ["role.read", "retired.permission"]),
];

beforeEach(() => {
  vi.clearAllMocks();
  listPermissions.mockResolvedValue(PERMISSIONS);
});

function renderDialog(onCreate = vi.fn().mockResolvedValue(undefined), onClose = vi.fn()) {
  renderWithIntl(<CreateRoleDialog open roles={ROLES} onCreate={onCreate} onClose={onClose} />);
  return { onCreate, onClose };
}

describe("CreateRoleDialog", () => {
  it("creates the role with the name and description typed, then closes", async () => {
    const { onCreate, onClose } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "  Grader ");
    await userEvent.type(screen.getByLabelText("Description"), "Marks submissions.");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({ name: "Grader", description: "Marks submissions." });
    expect(onClose).toHaveBeenCalled();
  });

  it("sends no description when none is typed", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({ name: "Grader", description: null });
  });

  it("can't create a role without a name", () => {
    renderDialog();

    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  it("says so under the name when a role already has it, and stays open", async () => {
    const onCreate = vi
      .fn()
      .mockRejectedValue(
        new ApiRequestError({ message: "Role already exists: Grader", fieldErrors: {} }, 409),
      );
    const { onClose } = renderDialog(onCreate);

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByText("A role with this name already exists.")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("says so when creating fails for another reason", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderDialog(vi.fn().mockRejectedValue(new Error("network down")));

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByText("Couldn't create the role. Try again.")).toBeInTheDocument();
  });

  it("starts the role with no permissions unless told otherwise", () => {
    renderDialog();

    expect(screen.getByRole("radio", { name: "No permissions" })).toBeChecked();
    expect(listPermissions).not.toHaveBeenCalled();
  });

  it("copies the declared permissions of the role chosen to start from", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A copy of another role" }));
    await userEvent.selectOptions(screen.getByLabelText("Role to copy"), "Course author");
    await userEvent.click(await screen.findByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["role.read"],
    });
  });

  it("offers every role to copy by its readable name, the first chosen", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A copy of another role" }));

    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Sparkth user", "Course author"]);
    await userEvent.click(await screen.findByRole("button", { name: "Create" }));
    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["group.read"],
    });
  });

  it("loads the permissions once, however often the start changes", async () => {
    renderDialog();

    await userEvent.click(screen.getByRole("radio", { name: "A copy of another role" }));
    await screen.findByRole("button", { name: "Create" });
    await userEvent.click(screen.getByRole("radio", { name: "No permissions" }));
    await userEvent.click(screen.getByRole("radio", { name: "A copy of another role" }));

    expect(listPermissions).toHaveBeenCalledTimes(1);
    expect(listPermissions).toHaveBeenCalledWith("test-token");
  });

  it("says so and won't create when the permissions can't be loaded", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    listPermissions.mockRejectedValue(new Error("network down"));
    renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A copy of another role" }));

    expect(
      await screen.findByText("Couldn't load the permissions. Try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  it("closes without creating on Cancel", async () => {
    const { onCreate, onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(onCreate).not.toHaveBeenCalled();
  });
});
