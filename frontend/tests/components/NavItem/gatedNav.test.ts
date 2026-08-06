import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/permissions", () => ({ checkPermission: vi.fn() }));

import { checkPermission } from "@/lib/permissions";
import { GATED_NAV, resolveNavPermissions, type GatedNavItem } from "@/components/NavItem/gatedNav";

const noopIcon = () => null;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GATED_NAV config", () => {
  it("declares the analytics and admin entries with their permissions/scopes", () => {
    expect(GATED_NAV.map((i) => i.key)).toEqual(["analytics", "admin"]);
    const analytics = GATED_NAV.find((i) => i.key === "analytics")!;
    const admin = GATED_NAV.find((i) => i.key === "admin")!;
    expect(analytics.permission).toBe("analytics.read");
    expect(analytics.scope).toBeUndefined();
    expect(admin.permission).toBe("email.whitelist.read");
    expect(admin.scope).toBe("whitelist");
    expect(admin.route).toBe("admin/whitelist");
    expect(admin.activeKey).toBe("admin");
  });
});

describe("resolveNavPermissions", () => {
  it("returns a map keyed by item key with each check's result", async () => {
    vi.mocked(checkPermission).mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    const items: GatedNavItem[] = [
      { key: "a", label: "A", icon: noopIcon, route: "a", permission: "analytics.read" },
      {
        key: "b",
        label: "B",
        icon: noopIcon,
        route: "b",
        permission: "email.whitelist.read",
        scope: "whitelist",
      },
    ];

    expect(await resolveNavPermissions("tok", items)).toEqual({ a: true, b: false });
  });

  it("passes each item's permission and scope through to checkPermission", async () => {
    vi.mocked(checkPermission).mockResolvedValue(true);
    const items: GatedNavItem[] = [
      {
        key: "b",
        label: "B",
        icon: noopIcon,
        route: "b",
        permission: "email.whitelist.read",
        scope: "whitelist",
      },
    ];

    await resolveNavPermissions("tok", items);

    expect(checkPermission).toHaveBeenCalledWith("tok", "email.whitelist.read", {
      scope: "whitelist",
    });
  });

  it("fails closed (false) when an item's check rejects", async () => {
    vi.mocked(checkPermission).mockRejectedValueOnce(new Error("network"));
    const items: GatedNavItem[] = [
      { key: "a", label: "A", icon: noopIcon, route: "a", permission: "analytics.read" },
    ];

    expect(await resolveNavPermissions("tok", items)).toEqual({ a: false });
  });
});
