import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const listRoles = vi.hoisted(() => vi.fn());
vi.mock("@/core/permissions/client", () => ({ listRoles }));

import RolesPage from "@/app/dashboard/permissions/roles/RolesPage";

describe("RolesPage", () => {
  it("lists the roles the caller may read", async () => {
    listRoles.mockResolvedValue([
      { id: 1, name: "admin", description: "Everything", permissions: [], is_builtin: true },
    ]);
    renderWithIntl(<RolesPage />);

    const list = await screen.findByRole("list", { name: "Roles" });
    expect(within(list).getByText("admin")).toBeInTheDocument();
    expect(listRoles).toHaveBeenCalledWith("test-token");
  });
});
