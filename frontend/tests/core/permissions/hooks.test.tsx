import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import {
  checkPermissions,
  listPermissions,
  type PermissionCheckQuery,
} from "@/core/permissions/client";
import {
  usePermissionCheck,
  usePermissionChecks,
  usePermissionList,
  useRoleAccess,
} from "@/core/permissions/hooks";
import type { PermissionResponse } from "@/core/permissions/types";

vi.mock("@/core/permissions/client", () => ({
  checkPermissions: vi.fn(),
  listPermissions: vi.fn(),
}));

const mockChecks = vi.mocked(checkPermissions);
const mockListPermissions = vi.mocked(listPermissions);

const PERMISSION_CHECKS: PermissionCheckQuery[] = [
  { permission: "email.whitelist.read", scope: "whitelist" },
  { permission: "email.whitelist.create", scope: "whitelist" },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("usePermissionCheck", () => {
  it("stays checking without a token", () => {
    const { result } = renderHook(() =>
      usePermissionCheck(null, "analytics.read", { scope: "global" }),
    );

    expect(result.current).toBe("checking");
    expect(mockChecks).not.toHaveBeenCalled();
  });

  it("asks its one check in a batch and is allowed when the backend grants it", async () => {
    mockChecks.mockResolvedValue([true]);

    const { result } = renderHook(() =>
      usePermissionCheck("tok", "email.whitelist.read", { scope: "whitelist" }),
    );

    await waitFor(() => expect(result.current).toBe("allowed"));
    expect(mockChecks).toHaveBeenCalledTimes(1);
    expect(mockChecks).toHaveBeenCalledWith("tok", [
      { permission: "email.whitelist.read", scope: "whitelist" },
    ]);
  });

  it("is denied when the backend refuses", async () => {
    mockChecks.mockResolvedValue([false]);

    const { result } = renderHook(() =>
      usePermissionCheck("tok", "analytics.read", { scope: "global" }),
    );

    await waitFor(() => expect(result.current).toBe("denied"));
  });

  it("fails closed when the check errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockChecks.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() =>
      usePermissionCheck("tok", "analytics.read", { scope: "global" }),
    );

    await waitFor(() => expect(result.current).toBe("denied"));
  });
});

describe("usePermissionChecks", () => {
  it("stays checking without a token", () => {
    const { result } = renderHook(() => usePermissionChecks(null, PERMISSION_CHECKS));

    expect(result.current).toEqual(["checking", "checking"]);
    expect(mockChecks).not.toHaveBeenCalled();
  });

  it("maps each answer to allowed or denied, in order", async () => {
    mockChecks.mockResolvedValue([true, false]);

    const { result } = renderHook(() => usePermissionChecks("tok", PERMISSION_CHECKS));

    await waitFor(() => expect(result.current).toEqual(["allowed", "denied"]));
    expect(mockChecks).toHaveBeenCalledWith("tok", PERMISSION_CHECKS);
  });

  it("denies every check when the batch errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockChecks.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePermissionChecks("tok", PERMISSION_CHECKS));

    await waitFor(() => expect(result.current).toEqual(["denied", "denied"]));
  });

  it("goes back to checking when the token changes, ignoring the old answers", async () => {
    let resolveOld: (answers: boolean[]) => void = () => {};
    mockChecks.mockReturnValueOnce(new Promise((resolve) => (resolveOld = resolve)));
    mockChecks.mockReturnValueOnce(new Promise(() => {}));

    const { result, rerender } = renderHook(
      ({ token }) => usePermissionChecks(token, PERMISSION_CHECKS),
      {
        initialProps: { token: "old" },
      },
    );
    rerender({ token: "new" });
    await act(async () => resolveOld([true, true]));

    expect(mockChecks).toHaveBeenCalledTimes(2);
    expect(result.current).toEqual(["checking", "checking"]);
  });

  it("asks once when given an inline checks array", async () => {
    mockChecks.mockResolvedValue([true]);

    const { result } = renderHook(() =>
      usePermissionChecks("tok", [{ permission: "analytics.read", scope: "global" }]),
    );
    await waitFor(() => expect(result.current).toEqual(["allowed"]));

    expect(mockChecks).toHaveBeenCalledTimes(1);
  });

  it("asks once across rerenders when the checks array is stable", async () => {
    mockChecks.mockResolvedValue([true, true]);

    const { result, rerender } = renderHook(() => usePermissionChecks("tok", PERMISSION_CHECKS));
    await waitFor(() => expect(result.current).toEqual(["allowed", "allowed"]));
    rerender();

    expect(mockChecks).toHaveBeenCalledTimes(1);
  });
});

const PERMISSIONS: PermissionResponse[] = [
  {
    name: "role.read",
    label: "See roles",
    description: "See roles.",
    category: "Users & access",
    risks: [],
    requires: [],
  },
];

describe("usePermissionList", () => {
  it("stays idle and asks nothing until loaded", () => {
    const { result } = renderHook(() => usePermissionList("tok"));

    expect(result.current.permissionList).toEqual({ status: "idle" });
    expect(mockListPermissions).not.toHaveBeenCalled();
  });

  it("loads the permissions when asked", async () => {
    mockListPermissions.mockResolvedValue(PERMISSIONS);
    const { result } = renderHook(() => usePermissionList("tok"));

    act(() => result.current.load());

    expect(result.current.permissionList).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.permissionList).toEqual({
        status: "loaded",
        permissions: PERMISSIONS,
      }),
    );
    expect(mockListPermissions).toHaveBeenCalledWith("tok");
  });

  it("loads once, however often it is asked", async () => {
    mockListPermissions.mockResolvedValue(PERMISSIONS);
    const { result } = renderHook(() => usePermissionList("tok"));

    act(() => result.current.load());
    act(() => result.current.load());
    await waitFor(() => expect(result.current.permissionList.status).toBe("loaded"));
    act(() => result.current.load());

    expect(mockListPermissions).toHaveBeenCalledTimes(1);
  });

  it("says so when loading fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockListPermissions.mockRejectedValue(new Error("network down"));
    const { result } = renderHook(() => usePermissionList("tok"));

    act(() => result.current.load());

    await waitFor(() => expect(result.current.permissionList).toEqual({ status: "failed" }));
  });

  it("asks again after a failure", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockListPermissions.mockRejectedValueOnce(new Error("network down"));
    mockListPermissions.mockResolvedValueOnce(PERMISSIONS);
    const { result } = renderHook(() => usePermissionList("tok"));

    act(() => result.current.load());
    await waitFor(() => expect(result.current.permissionList).toEqual({ status: "failed" }));
    act(() => result.current.load());

    await waitFor(() => expect(result.current.permissionList.status).toBe("loaded"));
    expect(mockListPermissions).toHaveBeenCalledTimes(2);
  });

  it("asks nothing without a token", () => {
    const { result } = renderHook(() => usePermissionList(null));

    act(() => result.current.load());

    expect(result.current.permissionList).toEqual({ status: "idle" });
    expect(mockListPermissions).not.toHaveBeenCalled();
  });
});

describe("useRoleAccess", () => {
  it("asks once about creating roles and changing or deleting the role named", async () => {
    mockChecks.mockResolvedValue([true, true, true, true]);

    const { result } = renderHook(() => useRoleAccess("tok", 7));

    await waitFor(() =>
      expect(result.current).toEqual({ canCreate: true, canChange: true, canDelete: true }),
    );
    expect(mockChecks).toHaveBeenCalledTimes(1);
    expect(mockChecks).toHaveBeenCalledWith("tok", [
      { permission: "role.create", scope: "global" },
      { permission: "role.update", scope: "global" },
      { permission: "role.update", scope: "role", scopeObjectId: "7" },
      { permission: "role.delete", scope: "role", scopeObjectId: "7" },
    ]);
  });

  it("asks about roles in general when no role is named", async () => {
    mockChecks.mockResolvedValue([true, true, true, true]);

    const { result } = renderHook(() => useRoleAccess("tok"));

    await waitFor(() => expect(result.current.canDelete).toBe(true));
    expect(mockChecks).toHaveBeenCalledWith("tok", [
      { permission: "role.create", scope: "global" },
      { permission: "role.update", scope: "global" },
      { permission: "role.update", scope: "role" },
      { permission: "role.delete", scope: "role" },
    ]);
  });

  it.each([
    ["role.create", [false, true, true, true]],
    ["role.update", [true, false, true, true]],
  ])("can't create without %s everywhere", async (_, answers) => {
    mockChecks.mockResolvedValue(answers);

    const { result } = renderHook(() => useRoleAccess("tok", 7));

    await waitFor(() => expect(result.current.canChange).toBe(true));
    expect(result.current.canCreate).toBe(false);
  });

  it("allows nothing until the answer arrives", () => {
    mockChecks.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useRoleAccess("tok", 7));

    expect(result.current).toEqual({ canCreate: false, canChange: false, canDelete: false });
  });
});
