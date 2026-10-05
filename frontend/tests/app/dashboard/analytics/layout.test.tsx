import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { redirect } from "next/navigation";
import { renderWithIntl } from "../../../intl-test-utils";

vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ token: "test-token" }) }));
vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  usePathname: () => "/dashboard/analytics/logins",
}));
const checkPermission = vi.hoisted(() => vi.fn());
vi.mock("@/lib/permissions", () => ({ checkPermission }));

import AnalyticsLayout from "@/app/dashboard/analytics/layout";

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("AnalyticsLayout", () => {
  it("checks analytics.read and renders the rail and the view when allowed", async () => {
    checkPermission.mockResolvedValue(true);
    renderWithIntl(
      <AnalyticsLayout>
        <p>view body</p>
      </AnalyticsLayout>,
    );
    expect(await screen.findByText("view body")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Analytics views" })).toBeInTheDocument();
    expect(checkPermission).toHaveBeenCalledWith("test-token", "analytics.read");
  });

  it("renders no view content while the check is pending", () => {
    checkPermission.mockReturnValue(new Promise(() => {}));
    renderWithIntl(
      <AnalyticsLayout>
        <p>view body</p>
      </AnalyticsLayout>,
    );
    expect(screen.queryByText("view body")).not.toBeInTheDocument();
  });

  it("redirects to the dashboard when denied", async () => {
    checkPermission.mockResolvedValue(false);
    renderWithIntl(
      <AnalyticsLayout>
        <p>view body</p>
      </AnalyticsLayout>,
    );
    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
  });

  it("fails closed when the check itself errors", async () => {
    checkPermission.mockRejectedValue(new Error("network down"));
    renderWithIntl(
      <AnalyticsLayout>
        <p>view body</p>
      </AnalyticsLayout>,
    );
    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
  });
});
