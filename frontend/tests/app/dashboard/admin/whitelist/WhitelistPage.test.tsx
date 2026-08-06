import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const auth = vi.hoisted(() => ({ token: "test-token" }));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: auth.token, user: { name: "A" } }),
}));
vi.mock("@/lib/permissions", () => ({ checkPermission: vi.fn() }));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, getWhitelist: vi.fn().mockResolvedValue([]) };
});

import { checkPermission } from "@/lib/permissions";
import { getWhitelist } from "@/lib/api";
import { redirect } from "next/navigation";
import WhitelistPage from "@/app/dashboard/admin/whitelist/WhitelistPage";

beforeEach(() => {
  vi.clearAllMocks();
  auth.token = "test-token";
});

describe("WhitelistPage access guard", () => {
  it("renders the page when the user holds email.whitelist.read", async () => {
    vi.mocked(checkPermission).mockResolvedValue(true);

    render(<WhitelistPage />);

    expect(await screen.findByText("Email Whitelist")).toBeInTheDocument();
    expect(checkPermission).toHaveBeenCalledWith("test-token", "email.whitelist.read", {
      scope: "whitelist",
    });
    expect(redirect).not.toHaveBeenCalled();
  });

  it("redirects to /dashboard when the user lacks the permission", async () => {
    vi.mocked(checkPermission).mockResolvedValue(false);

    render(<WhitelistPage />);

    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
  });

  it("resets to the checking state on a token change, not showing the prior user's page", async () => {
    auth.token = "token-A";
    vi.mocked(checkPermission)
      .mockResolvedValueOnce(true) // A: allowed
      .mockReturnValueOnce(new Promise<boolean>(() => {})); // B: still pending

    const { rerender } = render(<WhitelistPage />);
    expect(await screen.findByText("Email Whitelist")).toBeInTheDocument();

    auth.token = "token-B";
    rerender(<WhitelistPage />);

    // B's check hasn't settled: show the checking spinner, not the stale page.
    expect(await screen.findByText(/loading whitelist/i)).toBeInTheDocument();
    expect(screen.queryByText("Email Whitelist")).not.toBeInTheDocument();
  });

  it("does not fetch the whitelist for a denied user", async () => {
    // The fetch must be gated on access === "allowed": a denied user should never fire
    // getWhitelist (no wasted 403), matching the old synchronous is_admin guard.
    vi.mocked(checkPermission).mockResolvedValue(false);

    render(<WhitelistPage />);

    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
    expect(getWhitelist).not.toHaveBeenCalled();
  });
});
