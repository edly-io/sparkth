import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithIntl } from "@/tests/intl";
import { ApiRequestError } from "@/lib/api";
import { EditRoleDialog } from "@/core/permissions/components/ui/EditRoleDialog";

const ROLE = { name: "Grader", description: "Marks submissions." };

function renderDialog(onSave = vi.fn().mockResolvedValue(undefined), onClose = vi.fn()) {
  renderWithIntl(<EditRoleDialog open role={ROLE} onSave={onSave} onClose={onClose} />);
  return { onSave, onClose };
}

describe("EditRoleDialog", () => {
  it("starts from the role's name and description", () => {
    renderDialog();

    expect(screen.getByLabelText("Name")).toHaveValue("Grader");
    expect(screen.getByLabelText("Description")).toHaveValue("Marks submissions.");
  });

  it("can't save until something changes, nor with no name", async () => {
    renderDialog();
    const save = screen.getByRole("button", { name: "Save" });

    expect(save).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("Name"));
    expect(save).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Name"), "Reviewer");
    expect(save).toBeEnabled();
  });

  it("saves only what changed, trimmed, then closes", async () => {
    const { onSave, onClose } = renderDialog();

    await userEvent.clear(screen.getByLabelText("Name"));
    await userEvent.type(screen.getByLabelText("Name"), "  Reviewer ");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSave).toHaveBeenCalledWith({ name: "Reviewer" });
    expect(onClose).toHaveBeenCalled();
  });

  it("saves a description cleared to nothing as empty", async () => {
    const { onSave } = renderDialog();

    await userEvent.clear(screen.getByLabelText("Description"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSave).toHaveBeenCalledWith({ description: "" });
  });

  it("says so under the name when another role has it, and stays open", async () => {
    const onSave = vi
      .fn()
      .mockRejectedValue(
        new ApiRequestError({ message: "Role already exists: Reviewer", fieldErrors: {} }, 409),
      );
    const { onClose } = renderDialog(onSave);

    await userEvent.clear(screen.getByLabelText("Name"));
    await userEvent.type(screen.getByLabelText("Name"), "Reviewer");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("A role with this name already exists.")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("says so when saving fails for another reason, keeping what was typed", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    renderDialog(vi.fn().mockRejectedValue(new Error("network down")));

    await userEvent.type(screen.getByLabelText("Description"), " And reviews.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Couldn't save the role. Try again.")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toHaveValue("Marks submissions. And reviews.");
  });

  it("closes without saving on Cancel", async () => {
    const { onSave, onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });
});
