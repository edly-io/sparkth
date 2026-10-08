import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import PxcActivities from "@/plugins/pxc/PxcActivities";
import { getActivityEmbedUrl, listActivities } from "@/plugins/pxc/client";
import pxcEn from "@/plugins/pxc/messages/en.json";
import { renderWithIntl } from "@/tests/intl-test-utils";

const searchParams = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams.value,
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/client", () => ({
  listActivities: vi.fn(),
  getActivityEmbedUrl: vi.fn(),
}));

describe("PxcActivities", () => {
  beforeEach(() => {
    vi.mocked(listActivities).mockReset().mockResolvedValue([]);
    vi.mocked(getActivityEmbedUrl).mockReset().mockResolvedValue("/api/v1/pxc/embed?token=t");
  });

  it("shows the activity list when no activity is selected", async () => {
    searchParams.value = new URLSearchParams();

    renderWithIntl(<PxcActivities />, pxcEn);

    expect(await screen.findByText("No activities yet")).toBeInTheDocument();
    expect(getActivityEmbedUrl).not.toHaveBeenCalled();
  });

  it("shows the preview of the activity named in the query string", async () => {
    searchParams.value = new URLSearchParams("activity=act-1");

    renderWithIntl(<PxcActivities />, pxcEn);

    expect(await screen.findByTitle("Activity preview")).toBeInTheDocument();
    expect(getActivityEmbedUrl).toHaveBeenCalledWith(
      "test-token",
      "act-1",
      "play",
      expect.any(AbortSignal),
    );
    expect(listActivities).not.toHaveBeenCalled();
  });

  it("opens the author view when the query string asks for it", async () => {
    searchParams.value = new URLSearchParams("activity=act-1&as=edit");

    renderWithIntl(<PxcActivities />, pxcEn);

    expect(await screen.findByTitle("Activity preview")).toBeInTheDocument();
    expect(getActivityEmbedUrl).toHaveBeenCalledWith(
      "test-token",
      "act-1",
      "edit",
      expect.any(AbortSignal),
    );
  });
});
