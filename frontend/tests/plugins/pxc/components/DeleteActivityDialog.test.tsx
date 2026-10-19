import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { deleteActivity } from "@/plugins/pxc/client";
import { DeleteActivityDialog } from "@/plugins/pxc/components/DeleteActivityDialog";
import pxcEn from "@/plugins/pxc/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/client", () => ({
  deleteActivity: vi.fn(),
}));

const ACTIVITY = {
  id: "0192f0c4-0000-7000-8000-000000000001",
  title: "Photosynthesis quiz",
  description: "Five questions on light reactions",
  created_at: "2026-09-30T12:00:00Z",
  placed: false,
  preview_url: "/dashboard/pxc?activity=0192f0c4-0000-7000-8000-000000000001",
};

const PLACED_TEXT = pxcEn.pxc.deletePlacedBody;
const DRAFT_TEXT = pxcEn.pxc.deleteDraftBody;

function renderDialog(activity = ACTIVITY) {
  const onClose = vi.fn();
  const onDeleted = vi.fn();
  renderWithIntl(
    <DeleteActivityDialog activity={activity} onClose={onClose} onDeleted={onDeleted} />,
    pxcEn,
  );
  return { onClose, onDeleted };
}

describe("DeleteActivityDialog", () => {
  beforeEach(() => {
    vi.mocked(deleteActivity).mockReset();
  });

  it("warns that a placed activity may still be in a course", () => {
    renderDialog({ ...ACTIVITY, placed: true });

    expect(screen.getByText(PLACED_TEXT)).toBeInTheDocument();
    expect(screen.queryByText(DRAFT_TEXT)).not.toBeInTheDocument();
  });

  it("tells a draft's author the delete is permanent", () => {
    renderDialog();

    expect(screen.getByText(DRAFT_TEXT)).toBeInTheDocument();
    expect(screen.queryByText(PLACED_TEXT)).not.toBeInTheDocument();
  });

  it("deletes the activity and reports it on confirm", async () => {
    vi.mocked(deleteActivity).mockResolvedValue(undefined);
    const { onDeleted } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(deleteActivity).toHaveBeenCalledWith("test-token", ACTIVITY.id);
    expect(onDeleted).toHaveBeenCalledWith(ACTIVITY.id);
  });

  it("treats an activity that is already gone as deleted", async () => {
    vi.mocked(deleteActivity).mockRejectedValue(
      new ApiRequestError({ message: "nope", fieldErrors: {} }, 404),
    );
    const { onDeleted } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onDeleted).toHaveBeenCalledWith(ACTIVITY.id);
  });

  it("keeps the dialog open with an error when the delete fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(deleteActivity).mockRejectedValue(
      new ApiRequestError({ message: "boom", fieldErrors: {} }, 500),
    );
    const { onDeleted } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByText("Could not delete the activity.")).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });

  it("ignores Escape while the delete is running", async () => {
    vi.mocked(deleteActivity).mockReturnValue(new Promise(() => {}));
    const { onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.keyboard("{Escape}");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("deletes nothing on cancel", async () => {
    const { onClose } = renderDialog();

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(deleteActivity).not.toHaveBeenCalled();
  });
});
