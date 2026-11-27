import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import en from "@/core/i18n/catalogs/en";
import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";
import type { RoleResponse } from "@/core/permissions/types";

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

const ROLES = [
  role(1, "sparkth_user", ["group.read"]),
  role(2, "Course author", ["role.read", "retired.permission"]),
];

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

  it("closes without creating on Cancel", async () => {
    const { onCreate, onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(onCreate).not.toHaveBeenCalled();
  });
});
