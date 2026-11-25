import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const listGroups = vi.hoisted(() => vi.fn());
vi.mock("@/core/permissions/client", () => ({ listGroups }));

import GroupsPage from "@/app/dashboard/permissions/groups/GroupsPage";

describe("GroupsPage", () => {
  it("lists the groups the caller may read", async () => {
    listGroups.mockResolvedValue([{ id: 3, name: "Editors", description: null }]);
    renderWithIntl(<GroupsPage />);

    const list = await screen.findByRole("list", { name: "Groups" });
    expect(within(list).getByText("Editors")).toBeInTheDocument();
    expect(listGroups).toHaveBeenCalledWith("test-token");
  });
});
