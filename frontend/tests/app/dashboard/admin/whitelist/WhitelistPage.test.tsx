import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const auth = vi.hoisted(() => ({ token: "test-token" }));
vi.mock("@/core/auth/hooks", () => ({
  useAuth: () => ({ token: auth.token, user: { name: "A" } }),
}));
vi.mock("@/lib/permissions/client", () => ({ checkPermission: vi.fn() }));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, getWhitelist: vi.fn().mockResolvedValue([]), removeWhitelistEntry: vi.fn() };
});

import { checkPermission } from "@/lib/permissions/client";
import { ApiRequestError, getWhitelist, removeWhitelistEntry } from "@/lib/api";
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
    vi.mocked(checkPermission).mockImplementation(
      (token) => (token === "token-A" ? Promise.resolve(true) : new Promise<boolean>(() => {})), // B: still pending
    );

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
    // getWhitelist (no wasted 403).
    vi.mocked(checkPermission).mockResolvedValue(false);

    render(<WhitelistPage />);

    await waitFor(() => expect(redirect).toHaveBeenCalledWith("/dashboard"));
    expect(getWhitelist).not.toHaveBeenCalled();
  });
});

const ENTRY = {
  id: 7,
  value: "@example.com",
  entry_type: "domain",
  created_at: "2026-10-01T00:00:00Z",
};

async function confirmRemoval() {
  vi.mocked(checkPermission).mockResolvedValue(true);
  vi.mocked(getWhitelist).mockResolvedValueOnce([ENTRY]);
  render(<WhitelistPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Remove @example.com" }));
  await userEvent.click(screen.getByRole("button", { name: "Remove" }));
}

function grant(...granted: string[]) {
  vi.mocked(checkPermission).mockImplementation(async (_token, permission) =>
    granted.includes(permission),
  );
}

const ADD_INPUT = /user@example.com/;
const REMOVE_BUTTON = { name: "Remove @example.com" };

describe("WhitelistPage write controls", () => {
  beforeEach(() => {
    vi.mocked(getWhitelist).mockResolvedValue([ENTRY]);
  });

  it("hides Add and Remove from a user who may only read", async () => {
    grant("email.whitelist.read");

    render(<WhitelistPage />);

    expect(await screen.findByText("@example.com")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(ADD_INPUT)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", REMOVE_BUTTON)).not.toBeInTheDocument();
  });

  it("shows only Add to a user who may add but not remove", async () => {
    grant("email.whitelist.read", "email.whitelist.create");

    render(<WhitelistPage />);

    expect(await screen.findByPlaceholderText(ADD_INPUT)).toBeInTheDocument();
    expect(screen.queryByRole("button", REMOVE_BUTTON)).not.toBeInTheDocument();
  });

  it("shows only Remove to a user who may remove but not add", async () => {
    grant("email.whitelist.read", "email.whitelist.delete");

    render(<WhitelistPage />);

    expect(await screen.findByRole("button", REMOVE_BUTTON)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(ADD_INPUT)).not.toBeInTheDocument();
  });

  it("hides both controls while the create and delete checks are pending", async () => {
    vi.mocked(checkPermission).mockImplementation((_token, permission) =>
      permission === "email.whitelist.read"
        ? Promise.resolve(true)
        : new Promise<boolean>(() => {}),
    );

    render(<WhitelistPage />);

    expect(await screen.findByText("@example.com")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(ADD_INPUT)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", REMOVE_BUTTON)).not.toBeInTheDocument();
  });

  it("checks create and delete at the whitelist scope", async () => {
    grant("email.whitelist.read", "email.whitelist.create", "email.whitelist.delete");

    render(<WhitelistPage />);

    await screen.findByPlaceholderText(ADD_INPUT);
    for (const permission of ["email.whitelist.create", "email.whitelist.delete"]) {
      expect(checkPermission).toHaveBeenCalledWith("test-token", permission, {
        scope: "whitelist",
      });
    }
  });
});

describe("WhitelistPage removal", () => {
  it("removes an entry after confirming", async () => {
    vi.mocked(removeWhitelistEntry).mockResolvedValue(undefined);

    await confirmRemoval();

    expect(removeWhitelistEntry).toHaveBeenCalledWith("test-token", ENTRY.id);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps the dialog open with an error when removal fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(removeWhitelistEntry).mockRejectedValue(new Error("boom"));

    await confirmRemoval();

    expect(await screen.findByText("Failed to remove the entry.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows the backend's reason when removal is rejected", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(removeWhitelistEntry).mockRejectedValue(
      new ApiRequestError({ message: "Whitelist entry not found", fieldErrors: {} }, 404),
    );

    await confirmRemoval();

    expect(await screen.findByText("Whitelist entry not found")).toBeInTheDocument();
  });
});
