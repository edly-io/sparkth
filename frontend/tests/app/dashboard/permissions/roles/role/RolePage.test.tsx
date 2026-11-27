import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const nav = vi.hoisted(() => ({ query: "id=7" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.query),
  usePathname: () => "/dashboard/permissions/roles/role",
}));
const client = vi.hoisted(() => ({ getRole: vi.fn(), listPermissions: vi.fn() }));
vi.mock("@/core/permissions/client", () => client);
const { getRole, listPermissions } = client;

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
  getRole.mockResolvedValue(ROLE);
  listPermissions.mockResolvedValue([
    permission("role.read", "See roles"),
    permission("role.update", "Edit roles"),
  ]);
  vi.spyOn(console, "error").mockImplementation(() => {});
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

  it("lists every permission with the role's own ticked", async () => {
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
  });

  it("says so when the role can't be loaded", async () => {
    getRole.mockRejectedValue(new Error("network down"));
    renderWithIntl(<RolePage />);

    expect(await screen.findByText("Couldn't load the role. Try again later.")).toBeInTheDocument();
  });
});
