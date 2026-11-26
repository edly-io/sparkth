import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import en from "@/core/i18n/catalogs/en";
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

  it("duplicates the permissions of the role selected, as the role holds them", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A duplicate of another role" }));
    await userEvent.selectOptions(screen.getByLabelText("Role to duplicate"), "Course author");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["role.read", "retired.permission"],
    });
  });

  it("offers every role to duplicate by its readable name, the first selected", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A duplicate of another role" }));

    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Sparkth user", "Course author"]);
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["group.read"],
    });
  });

  it("duplicates the first role when the roles arrive after the dialog opened", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const dialog = (roles: RoleResponse[]) => (
      <CreateRoleDialog open roles={roles} onCreate={onCreate} onClose={vi.fn()} />
    );
    const { rerender } = renderWithIntl(dialog([]));
    rerender(
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
        {dialog(ROLES)}
      </NextIntlClientProvider>,
    );

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A duplicate of another role" }));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["group.read"],
    });
  });

  it("says so, creating nothing, when the role selected is no longer listed", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const dialog = (roles: RoleResponse[]) => (
      <CreateRoleDialog open roles={roles} onCreate={onCreate} onClose={vi.fn()} />
    );
    const { rerender } = renderWithIntl(dialog(ROLES));
    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "A duplicate of another role" }));
    await userEvent.selectOptions(screen.getByLabelText("Role to duplicate"), "Course author");
    rerender(
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
        {dialog([ROLES[0]])}
      </NextIntlClientProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByText("Couldn't create the role. Try again.")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("creates the role with the permissions chosen", async () => {
    const { onCreate } = renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "Choose permissions" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: "See roles" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "See groups" }));
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: null,
      permissions: ["role.read", "group.read"],
    });
  });

  it("shows a spinner and can't create while the permissions load", async () => {
    let finishLoading: (permissions: PermissionResponse[]) => void = () => {};
    listPermissions.mockReturnValue(
      new Promise<PermissionResponse[]>((resolve) => {
        finishLoading = resolve;
      }),
    );
    renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "Choose permissions" }));

    expect(screen.getByRole("status", { name: "Loading the permissions…" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    await act(async () => finishLoading(PERMISSIONS));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "See roles" })).toBeInTheDocument();
  });

  it("loads the permissions once, however often the start changes", async () => {
    renderDialog();

    await userEvent.click(screen.getByRole("radio", { name: "Choose permissions" }));
    await screen.findByRole("checkbox", { name: "See roles" });
    await userEvent.click(screen.getByRole("radio", { name: "A duplicate of another role" }));
    await userEvent.click(screen.getByRole("radio", { name: "Choose permissions" }));

    expect(listPermissions).toHaveBeenCalledTimes(1);
    expect(listPermissions).toHaveBeenCalledWith("test-token");
  });

  it("says so and won't create when the permissions can't be loaded", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    listPermissions.mockRejectedValue(new Error("network down"));
    renderDialog();

    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("radio", { name: "Choose permissions" }));

    expect(
      await screen.findByText("Couldn't load the permissions. Try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  it("can start as a duplicate of the role it is given, with its description", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    renderWithIntl(
      <CreateRoleDialog
        open
        roles={[{ ...ROLES[1], description: "Builds courses." }]}
        initialPermissionSource="duplicate"
        onCreate={onCreate}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("radio", { name: "A duplicate of another role" })).toBeChecked();
    expect(screen.getByLabelText("Description")).toHaveValue("Builds courses.");
    await userEvent.type(screen.getByLabelText("Name"), "Grader");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(onCreate).toHaveBeenCalledWith({
      name: "Grader",
      description: "Builds courses.",
      permissions: ["role.read", "retired.permission"],
    });
  });

  it("closes without creating on Cancel", async () => {
    const { onCreate, onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(onCreate).not.toHaveBeenCalled();
  });
});
