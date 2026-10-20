import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { checkPermission } from "@/lib/permissions/client";
import { usePermission } from "@/lib/permissions/usePermission";

vi.mock("@/lib/permissions/client", () => ({ checkPermission: vi.fn() }));

const mockCheck = vi.mocked(checkPermission);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("usePermission", () => {
  it("stays checking without a token", () => {
    const { result } = renderHook(() => usePermission(null, "analytics.read"));

    expect(result.current).toBe("checking");
    expect(mockCheck).not.toHaveBeenCalled();
  });

  it("is allowed when the backend grants the permission", async () => {
    mockCheck.mockResolvedValue(true);

    const { result } = renderHook(() =>
      usePermission("tok", "email.whitelist.read", { scope: "whitelist" }),
    );

    await waitFor(() => expect(result.current).toBe("allowed"));
    expect(mockCheck).toHaveBeenCalledWith("tok", "email.whitelist.read", { scope: "whitelist" });
  });

  it("is denied when the backend refuses", async () => {
    mockCheck.mockResolvedValue(false);

    const { result } = renderHook(() => usePermission("tok", "analytics.read"));

    await waitFor(() => expect(result.current).toBe("denied"));
  });

  it("fails closed when the check errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    mockCheck.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => usePermission("tok", "analytics.read"));

    await waitFor(() => expect(result.current).toBe("denied"));
  });

  it("goes back to checking when the token changes, ignoring the old answer", async () => {
    let resolveOld: (allowed: boolean) => void = () => {};
    mockCheck.mockReturnValueOnce(new Promise((resolve) => (resolveOld = resolve)));
    mockCheck.mockReturnValueOnce(new Promise(() => {}));

    const { result, rerender } = renderHook(({ token }) => usePermission(token, "analytics.read"), {
      initialProps: { token: "old" },
    });
    rerender({ token: "new" });
    resolveOld(true);

    await waitFor(() => expect(mockCheck).toHaveBeenCalledTimes(2));
    expect(result.current).toBe("checking");
  });
});
