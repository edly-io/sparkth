import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  checkPermission,
  checkPermissions,
  type PermissionQuestion,
} from "@/core/permissions/client";
import { usePermissionCheck, usePermissionChecks } from "@/core/permissions/hooks";

vi.mock("@/core/permissions/client", () => ({
  checkPermission: vi.fn(),
  checkPermissions: vi.fn(),
}));

const mockCheck = vi.mocked(checkPermission);
const mockChecks = vi.mocked(checkPermissions);

const QUESTIONS: PermissionQuestion[] = [
  { permission: "email.whitelist.read", scope: "whitelist" },
  { permission: "email.whitelist.create", scope: "whitelist" },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("usePermissionCheck", () => {
  it("stays checking without a token", () => {
    const { result } = renderHook(() => usePermissionCheck(null, "analytics.read"));

    expect(result.current).toBe("checking");
    expect(mockCheck).not.toHaveBeenCalled();
  });

  it("is allowed when the backend grants the permission", async () => {
    mockCheck.mockResolvedValue(true);

    const { result } = renderHook(() =>
      usePermissionCheck("tok", "email.whitelist.read", { scope: "whitelist" }),
    );

    await waitFor(() => expect(result.current).toBe("allowed"));
    expect(mockCheck).toHaveBeenCalledWith("tok", "email.whitelist.read", { scope: "whitelist" });
  });

  it("is denied when the backend refuses", async () => {
    mockCheck.mockResolvedValue(false);

    const { result } = renderHook(() => usePermissionCheck("tok", "analytics.read"));

    await waitFor(() => expect(result.current).toBe("denied"));
  });

  it("fails closed when the check errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockCheck.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePermissionCheck("tok", "analytics.read"));

    await waitFor(() => expect(result.current).toBe("denied"));
  });

  it("goes back to checking when the token changes, ignoring the old answer", async () => {
    let resolveOld: (allowed: boolean) => void = () => {};
    mockCheck.mockReturnValueOnce(new Promise((resolve) => (resolveOld = resolve)));
    mockCheck.mockReturnValueOnce(new Promise(() => {}));

    const { result, rerender } = renderHook(
      ({ token }) => usePermissionCheck(token, "analytics.read"),
      {
        initialProps: { token: "old" },
      },
    );
    rerender({ token: "new" });
    resolveOld(true);

    await waitFor(() => expect(mockCheck).toHaveBeenCalledTimes(2));
    expect(result.current).toBe("checking");
  });
});

describe("usePermissionChecks", () => {
  it("stays checking without a token", () => {
    const { result } = renderHook(() => usePermissionChecks(null, QUESTIONS));

    expect(result.current).toEqual(["checking", "checking"]);
    expect(mockChecks).not.toHaveBeenCalled();
  });

  it("maps each answer to allowed or denied, in order", async () => {
    mockChecks.mockResolvedValue([true, false]);

    const { result } = renderHook(() => usePermissionChecks("tok", QUESTIONS));

    await waitFor(() => expect(result.current).toEqual(["allowed", "denied"]));
    expect(mockChecks).toHaveBeenCalledWith("tok", QUESTIONS);
  });

  it("denies every question when the batch errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockChecks.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePermissionChecks("tok", QUESTIONS));

    await waitFor(() => expect(result.current).toEqual(["denied", "denied"]));
  });

  it("goes back to checking when the token changes, ignoring the old answers", async () => {
    let resolveOld: (answers: boolean[]) => void = () => {};
    mockChecks.mockReturnValueOnce(new Promise((resolve) => (resolveOld = resolve)));
    mockChecks.mockReturnValueOnce(new Promise(() => {}));

    const { result, rerender } = renderHook(({ token }) => usePermissionChecks(token, QUESTIONS), {
      initialProps: { token: "old" },
    });
    rerender({ token: "new" });
    resolveOld([true, true]);

    await waitFor(() => expect(mockChecks).toHaveBeenCalledTimes(2));
    expect(result.current).toEqual(["checking", "checking"]);
  });

  it("asks once across rerenders when the questions array is stable", async () => {
    mockChecks.mockResolvedValue([true, true]);

    const { result, rerender } = renderHook(() => usePermissionChecks("tok", QUESTIONS));
    await waitFor(() => expect(result.current).toEqual(["allowed", "allowed"]));
    rerender();

    expect(mockChecks).toHaveBeenCalledTimes(1);
  });
});
