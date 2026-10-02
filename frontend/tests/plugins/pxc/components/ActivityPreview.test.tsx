import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import { ActivityPreview } from "@/plugins/pxc/components/ActivityPreview";
import { getActivityEmbedUrl } from "@/plugins/pxc/client";
import pxcEn from "@/plugins/pxc/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/client", () => ({
  getActivityEmbedUrl: vi.fn(),
}));

const ACTIVITY_ID = "0192f0c4-0000-7000-8000-000000000001";

describe("ActivityPreview", () => {
  beforeEach(() => {
    vi.mocked(getActivityEmbedUrl).mockReset();
  });

  it("opens in the student view, iframing the play launch without same-origin", async () => {
    vi.mocked(getActivityEmbedUrl).mockResolvedValue("/api/v1/pxc/embed?token=play");

    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);

    const frame = await screen.findByTitle("Activity preview");
    expect(frame).toHaveAttribute("src", "/api/v1/pxc/embed?token=play");
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts allow-forms");
    expect(screen.getByRole("button", { name: "Student" })).toHaveAttribute("aria-pressed", "true");
    expect(getActivityEmbedUrl).toHaveBeenCalledWith(
      "test-token",
      ACTIVITY_ID,
      "play",
      expect.any(AbortSignal),
    );
  });

  it("refetches the launch under edit when the author view is chosen", async () => {
    vi.mocked(getActivityEmbedUrl).mockImplementation(
      async (_token, _id, permission) => `/api/v1/pxc/embed?token=${permission}`,
    );
    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);
    await screen.findByTitle("Activity preview");

    await userEvent.click(screen.getByRole("button", { name: "Author" }));

    expect(getActivityEmbedUrl).toHaveBeenLastCalledWith(
      "test-token",
      ACTIVITY_ID,
      "edit",
      expect.any(AbortSignal),
    );
    expect(await screen.findByTitle("Activity preview")).toHaveAttribute(
      "src",
      "/api/v1/pxc/embed?token=edit",
    );
    expect(screen.getByRole("button", { name: "Author" })).toHaveAttribute("aria-pressed", "true");
  });

  it("does not refetch when the current view is chosen again", async () => {
    vi.mocked(getActivityEmbedUrl).mockResolvedValue("/api/v1/pxc/embed?token=play");
    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);
    await screen.findByTitle("Activity preview");

    await userEvent.click(screen.getByRole("button", { name: "Student" }));

    expect(getActivityEmbedUrl).toHaveBeenCalledOnce();
    expect(screen.getByTitle("Activity preview")).toBeInTheDocument();
  });

  it("says the activity was not found on a 404", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(getActivityEmbedUrl).mockRejectedValue(
      new ApiRequestError({ message: "Activity not found", fieldErrors: {} }, 404),
    );

    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);

    expect(await screen.findByRole("alert")).toHaveTextContent("Activity not found");
    expect(screen.queryByTitle("Activity preview")).not.toBeInTheDocument();
  });

  it("reports a generic failure for any other error", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(getActivityEmbedUrl).mockRejectedValue(new Error("boom"));

    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load the activity. Please try again.",
    );
  });

  it("announces the loading state while the launch is pending", () => {
    vi.mocked(getActivityEmbedUrl).mockReturnValue(new Promise(() => {}));

    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);

    expect(screen.getByRole("status", { name: "Loading activity" })).toBeInTheDocument();
  });

  it("links back to the activity list", async () => {
    vi.mocked(getActivityEmbedUrl).mockResolvedValue("/api/v1/pxc/embed?token=play");

    renderWithIntl(<ActivityPreview activityId={ACTIVITY_ID} />, pxcEn);

    expect(screen.getByRole("link", { name: "Back to activities" })).toHaveAttribute(
      "href",
      "/dashboard/pxc",
    );
    await screen.findByTitle("Activity preview");
  });
});
