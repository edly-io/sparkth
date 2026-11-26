import { describe, it, expect, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { DeleteRoleDialog } from "@/core/permissions/components/ui/DeleteRoleDialog";
import type { RoleResponse } from "@/core/permissions/types";

function role(overrides: Partial<RoleResponse>): RoleResponse {
  return {
    id: 3,
    name: "grader",
    description: null,
    permissions: [],
    is_builtin: false,
    is_default: false,
    user_count: 0,
    group_count: 0,
    risks: [],
    ...overrides,
  };
}

describe("DeleteRoleDialog", () => {
  it("names the role and says which groups and people will lose it", () => {
    renderWithIntl(
      <DeleteRoleDialog
        role={role({ user_count: 2, group_count: 1 })}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Delete Grader?" })).toHaveTextContent(
      "1 group and 2 people will lose this role. This can't be undone.",
    );
  });

  it("says plainly when nobody holds the role", () => {
    renderWithIntl(<DeleteRoleDialog role={role({})} onConfirm={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByRole("dialog")).toHaveTextContent(
      "No one holds this role. This can't be undone.",
    );
  });

  it("deletes on Delete and closes without deleting on Cancel", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    renderWithIntl(<DeleteRoleDialog role={role({})} onConfirm={onConfirm} onClose={onClose} />);
    const dialog = screen.getByRole("dialog");

    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
