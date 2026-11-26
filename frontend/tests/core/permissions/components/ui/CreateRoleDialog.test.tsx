import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";

function renderDialog(onCreate = vi.fn().mockResolvedValue(undefined), onClose = vi.fn()) {
  renderWithIntl(<CreateRoleDialog open onCreate={onCreate} onClose={onClose} />);
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

  it("closes without creating on Cancel", async () => {
    const { onCreate, onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(onCreate).not.toHaveBeenCalled();
  });
});
