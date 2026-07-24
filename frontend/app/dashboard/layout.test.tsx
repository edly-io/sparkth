import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import DashboardLayout from "./layout";

// The layout's only job under test is deriving `canViewAnalytics` from the
// permission check, so stub every collaborator that would otherwise need a
// router, a network client or a plugin registry.
const auth = {
  token: "token-a" as string | null,
  user: { name: "A" },
  isAuthenticated: true,
  loading: false,
  logout: vi.fn(),
};

vi.mock("@/lib/plugins", () => ({}));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => auth }));
vi.mock("next/navigation", () => ({ redirect: vi.fn(), usePathname: () => "/dashboard" }));
vi.mock("@/lib/plugins/context", () => ({
  PluginProvider: ({ children }: { children: React.ReactNode }) => children,
  useEnabledPlugins: () => ({ plugins: [], loading: false }),
}));
vi.mock("@/components/MobileSidebar", () => ({ default: () => null }));
vi.mock("@/components/AppSidebar", () => ({
  default: ({ user }: { user?: { canViewAnalytics?: boolean } }) => (
    <div data-testid="analytics-flag">{String(user?.canViewAnalytics)}</div>
  ),
}));

const checkPermission = vi.hoisted(() => vi.fn());
vi.mock("@/lib/permissions", () => ({ checkPermission }));

describe("DashboardLayout analytics gating", () => {
  beforeEach(() => {
    auth.token = "token-a";
    checkPermission.mockReset();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const flag = () => screen.getByTestId("analytics-flag").textContent;

  it("grants the nav entry when the permission check allows it", async () => {
    checkPermission.mockResolvedValue(true);

    render(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(flag()).toBe("true"));
  });

  it("fails closed when the permission check rejects", async () => {
    checkPermission.mockRejectedValue(new Error("boom"));

    render(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(console.error).toHaveBeenCalled());
    expect(flag()).toBe("false");
  });

  it("revokes a previously granted entry when a re-check for a new token fails", async () => {
    checkPermission.mockResolvedValue(true);

    const { rerender } = render(<DashboardLayout>child</DashboardLayout>);
    await waitFor(() => expect(flag()).toBe("true"));

    // Re-login as someone else: the token changes and the re-check errors out.
    // The previous user's answer must not survive.
    checkPermission.mockRejectedValue(new Error("boom"));
    auth.token = "token-b";
    rerender(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(flag()).toBe("false"));
  });
});
