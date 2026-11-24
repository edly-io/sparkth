import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";
import type { RoleResponse } from "@/core/permissions/types";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const listRoles = vi.hoisted(() => vi.fn());
vi.mock("@/core/permissions/client", () => ({ listRoles }));

import RolesPage from "@/app/dashboard/permissions/roles/RolesPage";

function role(id: number, name: string, overrides: Partial<RoleResponse> = {}): RoleResponse {
  return {
    id,
    name,
    display_name: name,
    description: null,
    permissions: [],
    is_builtin: false,
    is_default: false,
    user_count: 0,
    group_count: 0,
    ...overrides,
  };
}

const ROLES = [
  role(1, "admin", { display_name: "Admin", is_builtin: true }),
  role(2, "sparkth_user", { display_name: "Sparkth user", is_builtin: true, is_default: true }),
  role(3, "Course author"),
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

async function findCardNames(): Promise<string[]> {
  const list = await screen.findByRole("list", { name: "Roles" });
  return within(list)
    .getAllByRole("heading")
    .map((heading) => heading.textContent ?? "");
}

describe("RolesPage", () => {
  it("shows a card for each role the caller may read, in the order listed", async () => {
    listRoles.mockResolvedValue(ROLES);
    renderWithIntl(<RolesPage />);

    expect(await findCardNames()).toEqual(["Admin", "Sparkth user", "Course author"]);
    expect(listRoles).toHaveBeenCalledWith("test-token");
  });

  it("says what a role is above the cards", async () => {
    listRoles.mockResolvedValue(ROLES);
    renderWithIntl(<RolesPage />);

    expect(await screen.findByText(/A role is a named set of permissions/)).toBeInTheDocument();
  });

  it("offers the list view as the current one and comparing permissions as not yet available", async () => {
    listRoles.mockResolvedValue(ROLES);
    renderWithIntl(<RolesPage />);

    const views = screen.getByRole("group", { name: "View" });
    expect(within(views).getByRole("link", { name: "List" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(views).getByRole("button", { name: "Compare permissions" })).toBeDisabled();
    await findCardNames();
  });

  it("says so when there are no roles", async () => {
    listRoles.mockResolvedValue([]);
    renderWithIntl(<RolesPage />);

    expect(await screen.findByText("No roles yet.")).toBeInTheDocument();
  });

  it("shows an error when the roles can't be loaded", async () => {
    listRoles.mockRejectedValue(new Error("boom"));
    renderWithIntl(<RolesPage />);

    expect(
      await screen.findByText("Couldn't load the roles. Try again later."),
    ).toBeInTheDocument();
  });
});
