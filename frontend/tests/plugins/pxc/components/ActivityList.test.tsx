import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ActivityList } from "@/plugins/pxc/components/ActivityList";
import { listActivities } from "@/plugins/pxc/client";
import pxcEn from "@/plugins/pxc/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/client", () => ({
  listActivities: vi.fn(),
}));

const ACTIVITY = {
  id: "0192f0c4-0000-7000-8000-000000000001",
  title: "Photosynthesis quiz",
  description: "Five questions on light reactions",
  created_at: "2026-09-30T12:00:00Z",
  preview_url: "/dashboard/pxc?activity=0192f0c4-0000-7000-8000-000000000001",
};

describe("ActivityList", () => {
  beforeEach(() => {
    vi.mocked(listActivities).mockReset();
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
});
