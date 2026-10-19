import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ActivityList } from "@/plugins/pxc/components/ActivityList";
import { deleteActivity, listActivities } from "@/plugins/pxc/client";
import pxcEn from "@/plugins/pxc/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/client", () => ({
  listActivities: vi.fn(),
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

describe("ActivityList", () => {
  beforeEach(() => {
    vi.mocked(listActivities).mockReset();
    vi.mocked(deleteActivity).mockReset();
  });

  it("lists each activity with its description, creation date and a Preview link", async () => {
    vi.mocked(listActivities).mockResolvedValue([ACTIVITY]);

    renderWithIntl(<ActivityList />, pxcEn);

    expect(await screen.findByRole("heading", { name: "Photosynthesis quiz" })).toBeInTheDocument();
    expect(screen.getByText("Five questions on light reactions")).toBeInTheDocument();
    expect(screen.getByText("Created Sep 30, 2026")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Preview Photosynthesis quiz" })).toHaveAttribute(
      "href",
      ACTIVITY.preview_url,
    );
    expect(listActivities).toHaveBeenCalledWith("test-token", expect.any(AbortSignal));
  });

  it("exposes a loading status while the list is fetching", () => {
    vi.mocked(listActivities).mockReturnValue(new Promise(() => {}));

    renderWithIntl(<ActivityList />, pxcEn);

    expect(screen.getByRole("status", { name: "Loading activities" })).toBeInTheDocument();
  });

  it("shows the empty state with a link to Compose when there are no activities", async () => {
    vi.mocked(listActivities).mockResolvedValue([]);

    renderWithIntl(<ActivityList />, pxcEn);

    expect(await screen.findByText("No activities yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Compose" })).toHaveAttribute(
      "href",
      "/dashboard/chat",
    );
  });

  it("shows an error when the list fails to load", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(listActivities).mockRejectedValue(new Error("boom"));

    renderWithIntl(<ActivityList />, pxcEn);

    expect(await screen.findByText("Could not load your activities.")).toBeInTheDocument();
  });

  it("refetches the list when Try again is clicked after a failure", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(listActivities)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce([ACTIVITY]);
    renderWithIntl(<ActivityList />, pxcEn);

    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "Photosynthesis quiz" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(listActivities).toHaveBeenCalledTimes(2);
  });

  it("marks a placed activity", async () => {
    const placed = {
      ...ACTIVITY,
      id: "0192f0c4-0000-7000-8000-000000000002",
      title: "Cell quiz",
      placed: true,
    };
    vi.mocked(listActivities).mockResolvedValue([ACTIVITY, placed]);

    renderWithIntl(<ActivityList />, pxcEn);

    const badge = await screen.findByText("Placed");
    expect(screen.getAllByText("Placed")).toHaveLength(1);
    expect(badge.closest("li")).toContainElement(
      screen.getByRole("heading", { name: "Cell quiz" }),
    );
  });

  it("removes an activity from the list once it is deleted", async () => {
    vi.mocked(listActivities).mockResolvedValue([ACTIVITY]);
    vi.mocked(deleteActivity).mockResolvedValue(undefined);
    renderWithIntl(<ActivityList />, pxcEn);

    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Photosynthesis quiz" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );

    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Photosynthesis quiz" }),
      ).not.toBeInTheDocument(),
    );
    expect(listActivities).toHaveBeenCalledTimes(1);
  });

  it("shows the empty state after the last activity is deleted", async () => {
    vi.mocked(listActivities).mockResolvedValue([ACTIVITY]);
    vi.mocked(deleteActivity).mockResolvedValue(undefined);
    renderWithIntl(<ActivityList />, pxcEn);

    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Photosynthesis quiz" }),
    );
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );

    expect(await screen.findByText("No activities yet")).toBeInTheDocument();
  });
});
