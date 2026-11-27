import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "@/tests/intl";

vi.mock("@/core/auth/hooks", () => ({ useAuth: () => ({ token: "test-token" }) }));
const checkPermissions = vi.hoisted(() => vi.fn());
vi.mock("@/core/permissions/client", () => ({ checkPermissions }));

import PermissionsLayout from "@/app/dashboard/permissions/layout";

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

function renderLayout() {
  renderWithIntl(
    <PermissionsLayout>
      <p>tab body</p>
    </PermissionsLayout>,
  );
}

describe("PermissionsLayout", () => {
  it("asks for permission.read, role.read and group.read in one request", async () => {
    checkPermissions.mockResolvedValue([true, true, true]);
    renderLayout();

    await screen.findByText("tab body");
    expect(checkPermissions).toHaveBeenCalledTimes(1);
    expect(checkPermissions).toHaveBeenCalledWith("test-token", [
      { permission: "permission.read", scope: "global" },
      { permission: "role.read", scope: "role" },
      { permission: "group.read", scope: "group" },
    ]);
  });

  it("shows its page when all three are granted, with no heading or tabs of its own", async () => {
    checkPermissions.mockResolvedValue([true, true, true]);
    renderLayout();

    expect(await screen.findByText("tab body")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it.each([
    ["permission.read", [false, true, true]],
    ["role.read", [true, false, true]],
    ["group.read", [true, true, false]],
  ])("refuses access without %s", async (_missing, answers) => {
    checkPermissions.mockResolvedValue(answers);
    renderLayout();

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Access sections" })).not.toBeInTheDocument();
  });

  it("refuses access when the check fails", async () => {
    checkPermissions.mockRejectedValue(new Error("network down"));
    renderLayout();

    expect(
      await screen.findByRole("heading", { name: "You don't have access to this page" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
  });

  it("shows no page while checking", () => {
    checkPermissions.mockReturnValue(new Promise(() => {}));
    renderLayout();

    expect(screen.queryByText("tab body")).not.toBeInTheDocument();
  });
});
