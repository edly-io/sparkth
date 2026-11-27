import { screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import PxcActivities from "@/plugins/pxc/src/pages/PxcActivities";
import { getActivityLaunch, listActivities } from "@/plugins/pxc/src/client";
import pxcEn from "@/plugins/pxc/src/i18n/en.json";
import { renderWithIntl } from "@/lib/testing/intl";

const searchParams = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams.value,
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/lib/auth/hooks", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

vi.mock("@/plugins/pxc/src/client", () => ({
  listActivities: vi.fn(),
  getActivityLaunch: vi.fn(),
}));

vi.mock("@/lib/permissions/client", () => ({
  checkPermissions: vi.fn().mockResolvedValue([true]),
}));

describe("PxcActivities", () => {
  beforeEach(() => {
    vi.mocked(listActivities).mockReset().mockResolvedValue([]);
    vi.mocked(getActivityLaunch)
      .mockReset()
      .mockResolvedValue({ embed_url: "/api/v1/pxc/embed?token=t", owner_user_id: 7 });
  });

  it("shows the activity list when no activity is selected", async () => {
    searchParams.value = new URLSearchParams();

    renderWithIntl(<PxcActivities />, pxcEn);

    expect(await screen.findByText("No activities yet")).toBeInTheDocument();
    expect(getActivityLaunch).not.toHaveBeenCalled();
  });

  it("shows the preview of the activity named in the query string", async () => {
    searchParams.value = new URLSearchParams("activity=act-1");

    renderWithIntl(<PxcActivities />, pxcEn);

    expect(await screen.findByTitle("Activity preview")).toBeInTheDocument();
    expect(getActivityLaunch).toHaveBeenCalledWith(
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
    expect(getActivityLaunch).toHaveBeenCalledWith(
      "test-token",
      "act-1",
      "edit",
      expect.any(AbortSignal),
    );
  });
});
