import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import DashboardLayout from "./layout";

// The layout's only job under test is resolving the gated-nav permission map and
// threading it to the sidebars, so stub every collaborator that would otherwise
// need a router, a network client or a plugin registry.
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
  default: ({ navPermissions }: { navPermissions?: Record<string, boolean> }) => (
    <div data-testid="nav-permissions">{JSON.stringify(navPermissions ?? null)}</div>
  ),
}));

const resolveNavPermissions = vi.hoisted(() => vi.fn());
vi.mock("@/components/NavItem", () => ({ resolveNavPermissions }));

describe("DashboardLayout nav permission gating", () => {
  beforeEach(() => {
    auth.token = "token-a";
    resolveNavPermissions.mockReset();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const permissions = () => screen.getByTestId("nav-permissions").textContent;

  it("threads the resolved permission map to the sidebar", async () => {
    resolveNavPermissions.mockResolvedValue({ analytics: true, admin: false });

    render(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() =>
      expect(permissions()).toBe(JSON.stringify({ analytics: true, admin: false })),
    );
  });

  it("grants nothing when resolution rejects outright", async () => {
    resolveNavPermissions.mockRejectedValue(new Error("boom"));

    render(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(console.error).toHaveBeenCalled());
    expect(permissions()).toBe("{}");
  });

  it("clears previously granted entries when a re-resolve for a new token fails", async () => {
    resolveNavPermissions.mockResolvedValue({ analytics: true, admin: true });

    const { rerender } = render(<DashboardLayout>child</DashboardLayout>);
    await waitFor(() =>
      expect(permissions()).toBe(JSON.stringify({ analytics: true, admin: true })),
    );

    // Re-login as someone else: the token changes and the re-resolve errors out.
    // The previous user's map must not survive.
    resolveNavPermissions.mockRejectedValue(new Error("boom"));
    auth.token = "token-b";
    rerender(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(permissions()).toBe("{}"));
  });

  it("clears the previous user's map immediately on a token change, before the re-resolve settles", async () => {
    resolveNavPermissions.mockResolvedValueOnce({ analytics: true, admin: true });

    const { rerender } = render(<DashboardLayout>child</DashboardLayout>);
    await waitFor(() =>
      expect(permissions()).toBe(JSON.stringify({ analytics: true, admin: true })),
    );

    // Re-login: new token, and the re-resolve is still in flight (never settles here). The
    // previous user's gated entries must not linger while the new checks are pending.
    resolveNavPermissions.mockReturnValueOnce(new Promise<Record<string, boolean>>(() => {}));
    auth.token = "token-b";
    rerender(<DashboardLayout>child</DashboardLayout>);

    await waitFor(() => expect(permissions()).toBe("{}"));
  });
});
