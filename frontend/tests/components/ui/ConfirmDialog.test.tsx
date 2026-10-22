import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

function renderDialog(onConfirm: () => Promise<void>) {
  const onClose = vi.fn();
  render(
    <ConfirmDialog
      title="Remove entry?"
      description="It stops working at once."
      confirmLabel="Remove"
      pendingLabel="Removing"
      cancelLabel="Cancel"
      errorMessage="Could not remove the entry."
      onConfirm={onConfirm}
      onClose={onClose}
    />,
  );
  return { onClose };
}

describe("ConfirmDialog", () => {
  it("shows the title and description", () => {
    renderDialog(vi.fn());

    expect(screen.getByRole("dialog", { name: "Remove entry?" })).toBeInTheDocument();
    expect(screen.getByText("It stops working at once.")).toBeInTheDocument();
  });

  it("runs the action on confirm", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const { onClose } = renderDialog(onConfirm);

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("stays open with the error when the action fails", async () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    const failure = new Error("boom");
    const { onClose } = renderDialog(vi.fn().mockRejectedValue(failure));

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(await screen.findByText("Could not remove the entry.")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(logged).toHaveBeenCalledWith("ConfirmDialog: action failed", failure);
  });

  it("cannot be dismissed while the action runs", async () => {
    const { onClose } = renderDialog(vi.fn().mockReturnValue(new Promise(() => {})));

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await userEvent.keyboard("{Escape}");

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("closes without running the action on cancel", async () => {
    const onConfirm = vi.fn();
    const { onClose } = renderDialog(onConfirm);

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("closes on Escape when idle", async () => {
    const { onClose } = renderDialog(vi.fn());

    await userEvent.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledOnce();
  });
});
