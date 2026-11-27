import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import en from "@/core/i18n/catalogs/en";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const nav = vi.hoisted(() => ({ query: "id=7" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.query),
  usePathname: () => "/dashboard/permissions/roles/role",
}));
const client = vi.hoisted(() => ({
  checkPermissions: vi.fn(),
  getRole: vi.fn(),
  listPermissions: vi.fn(),
  setRolePermissions: vi.fn(),
  updateRoleDetails: vi.fn(),
}));
vi.mock("@/core/permissions/client", () => client);
const { checkPermissions, getRole, listPermissions, setRolePermissions, updateRoleDetails } =
  client;

import RolePage from "@/app/dashboard/permissions/roles/role/RolePage";

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

const ROLE: RoleResponse = {
  id: 7,
  name: "course_author",
  description: "Builds and publishes courses.",
  permissions: ["role.read"],
  is_builtin: false,
  is_default: false,
  user_count: 0,
  group_count: 0,
  risks: ["delegates_access"],
};

beforeEach(() => {
  vi.clearAllMocks();
  nav.query = "id=7";
  checkPermissions.mockResolvedValue([true]);
  getRole.mockResolvedValue(ROLE);
  listPermissions.mockResolvedValue([
    permission("role.read", "See roles"),
    permission("role.update", "Edit roles"),
  ]);
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RolePage", () => {
  it("shows the role's name as its heading, with its badge, description and risks", async () => {
    renderWithIntl(<RolePage />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Course author" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.getByText("Builds and publishes courses.")).toBeInTheDocument();
    expect(screen.getByText("Can give others access")).toBeInTheDocument();
    expect(getRole).toHaveBeenCalledWith("test-token", 7);
  });

  it("leads back to Roles, under Access & permissions", async () => {
    renderWithIntl(<RolePage />);

    const breadcrumb = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(breadcrumb).getByText("Access & permissions")).not.toHaveAttribute("href");
    expect(within(breadcrumb).getByRole("link", { name: "Roles" })).toHaveAttribute(
      "href",
      "/dashboard/permissions/roles",
    );
    expect(within(breadcrumb).getByText("Course author")).toHaveAttribute("aria-current", "page");
  });

  it("lists every permission with the role's own checked", async () => {
    renderWithIntl(<RolePage />);

    expect(await screen.findByRole("checkbox", { name: "See roles" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).not.toBeChecked();
    expect(listPermissions).toHaveBeenCalledTimes(1);
  });

  it("shows a spinner while the permissions load", async () => {
    listPermissions.mockReturnValue(new Promise(() => {}));
    renderWithIntl(<RolePage />);

    await screen.findByRole("heading", { level: 1, name: "Course author" });
    expect(screen.getByRole("status", { name: "Loading the permissions…" })).toBeInTheDocument();
  });

  it("can't save until a permission is checked or unchecked, nor once it is put back", async () => {
    renderWithIntl(<RolePage />);

    const save = await screen.findByRole("button", { name: "Save changes" });
    expect(save).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Edit roles" }));
    expect(save).toBeEnabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Edit roles" }));
    expect(save).toBeDisabled();
  });

  it("saves every permission checked, keeping any no longer declared, and shows the saved role", async () => {
    getRole.mockResolvedValue({ ...ROLE, permissions: ["role.read", "retired.permission"] });
    setRolePermissions.mockResolvedValue({
      ...ROLE,
      permissions: ["role.read", "retired.permission", "role.update"],
      risks: ["delegates_access", "deletes"],
    });
    renderWithIntl(<RolePage />);

    await userEvent.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(setRolePermissions).toHaveBeenCalledWith("test-token", 7, [
      "role.read",
      "retired.permission",
      "role.update",
    ]);
    expect(await screen.findByText("Can delete")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).toBeChecked();
  });

  it("says the changes were saved, for a few seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setRolePermissions.mockResolvedValue({ ...ROLE, permissions: ["role.read", "role.update"] });
    renderWithIntl(<RolePage />);

    await user.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Saved");

    act(() => vi.advanceTimersByTime(3000));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("locks every permission while saving", async () => {
    let finishSaving: (role: RoleResponse) => void = () => {};
    setRolePermissions.mockReturnValue(
      new Promise<RoleResponse>((resolve) => {
        finishSaving = resolve;
      }),
    );
    renderWithIntl(<RolePage />);

    await userEvent.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    for (const checkbox of screen.getAllByRole("checkbox")) expect(checkbox).toBeDisabled();
    await act(async () => finishSaving({ ...ROLE, permissions: ["role.read", "role.update"] }));
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).toBeEnabled();
  });

  it("ignores a save that finishes after another role was opened", async () => {
    let finishSaving: (role: RoleResponse) => void = () => {};
    setRolePermissions.mockReturnValue(
      new Promise<RoleResponse>((resolve) => {
        finishSaving = resolve;
      }),
    );
    const { rerender } = renderWithIntl(<RolePage />);
    await userEvent.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    getRole.mockResolvedValue({ ...ROLE, id: 8, name: "reviewer" });
    nav.query = "id=8";
    rerender(
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={en}>
        <RolePage />
      </NextIntlClientProvider>,
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Reviewer" })).toBeInTheDocument();
    await act(async () => finishSaving({ ...ROLE, permissions: ["role.read", "role.update"] }));

    expect(screen.getByRole("heading", { level: 1, name: "Reviewer" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).not.toBeChecked();
  });

  it("says so when saving fails, keeping what was checked", async () => {
    setRolePermissions.mockRejectedValue(new Error("network down"));
    renderWithIntl(<RolePage />);

    await userEvent.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText("Couldn't save the permissions. Try again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  });

  it("edits the role's name and description, keeping unsaved permission changes", async () => {
    updateRoleDetails.mockResolvedValue({
      ...ROLE,
      name: "Reviewer",
      description: "Reviews work.",
    });
    renderWithIntl(<RolePage />);

    await userEvent.click(await screen.findByRole("checkbox", { name: "Edit roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.clear(screen.getByLabelText("Name"));
    await userEvent.type(screen.getByLabelText("Name"), "Reviewer");
    await userEvent.clear(screen.getByLabelText("Description"));
    await userEvent.type(screen.getByLabelText("Description"), "Reviews work.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(updateRoleDetails).toHaveBeenCalledWith("test-token", 7, {
      name: "Reviewer",
      description: "Reviews work.",
    });
    expect(await screen.findByRole("heading", { level: 1, name: "Reviewer" })).toBeInTheDocument();
    expect(screen.getByText("Reviews work.")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Edit roles" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  });

  it("lets nobody change a built-in role's permissions", async () => {
    getRole.mockResolvedValue({ ...ROLE, is_builtin: true });
    renderWithIntl(<RolePage />);

    expect(await screen.findByRole("checkbox", { name: "Edit roles" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("lets only those who may change the role change its permissions", async () => {
    checkPermissions.mockResolvedValue([false]);
    renderWithIntl(<RolePage />);

    expect(await screen.findByRole("checkbox", { name: "Edit roles" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(checkPermissions).toHaveBeenCalledWith("test-token", [
      { permission: "role.update", scope: "role", scopeObjectId: "7" },
    ]);
  });

  it("says so when there is no such role", async () => {
    getRole.mockRejectedValue(
      new ApiRequestError({ message: "Role not found: 7", fieldErrors: {} }, 404),
    );
    renderWithIntl(<RolePage />);

    expect(await screen.findByText("This role doesn't exist.")).toBeInTheDocument();
  });

  it("asks for nothing when the address names no role", async () => {
    nav.query = "id=abc";
    renderWithIntl(<RolePage />);

    expect(await screen.findByText("This role doesn't exist.")).toBeInTheDocument();
    expect(getRole).not.toHaveBeenCalled();
    expect(checkPermissions).not.toHaveBeenCalled();
  });

  it("says so when the role can't be loaded", async () => {
    getRole.mockRejectedValue(new Error("network down"));
    renderWithIntl(<RolePage />);

    expect(await screen.findByText("Couldn't load the role. Try again later.")).toBeInTheDocument();
  });
});
