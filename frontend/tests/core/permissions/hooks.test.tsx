import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import { checkPermissions, type PermissionCheckQuery } from "@/core/permissions/client";
import { usePermissionCheck, usePermissionChecks } from "@/core/permissions/hooks";

vi.mock("@/core/permissions/client", () => ({ checkPermissions: vi.fn() }));

const mockChecks = vi.mocked(checkPermissions);

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
