import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/core/permissions/client", () => ({ checkPermission: vi.fn() }));

import { checkPermission } from "@/core/permissions/client";
import {
  GATED_SIDEBAR_LINKS,
  resolveSidebarPermissions,
  type GatedSidebarLink,
} from "@/core/sidebar/gatedSidebarLinks";

const noopIcon = () => null;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GATED_SIDEBAR_LINKS config", () => {
  it("declares the analytics, admin and audit entries with their permissions/scopes", () => {
    expect(GATED_SIDEBAR_LINKS.map((link) => link.key)).toEqual(["analytics", "admin", "audit"]);
    const analytics = GATED_SIDEBAR_LINKS.find((link) => link.key === "analytics")!;
    const admin = GATED_SIDEBAR_LINKS.find((link) => link.key === "admin")!;
    expect(analytics.permission).toBe("analytics.read");
    expect(analytics.scope).toBeUndefined();
    expect(admin.permission).toBe("email.whitelist.read");
    expect(admin.scope).toBe("whitelist");
    expect(admin.route).toBe("admin/whitelist");
    expect(admin.activeKey).toBe("admin");
    const audit = GATED_SIDEBAR_LINKS.find((link) => link.key === "audit")!;
    expect(audit.permission).toBe("audit.read");
    expect(audit.scope).toBeUndefined();
    expect(audit.route).toBe("audit");
  });
});

describe("resolveSidebarPermissions", () => {
  it("returns a map keyed by link key with each check's result", async () => {
    vi.mocked(checkPermission).mockResolvedValueOnce(true).mockResolvedValueOnce(false);
    const links: GatedSidebarLink[] = [
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

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: true, b: false });
  });

  it("passes each link's permission and scope through to checkPermission", async () => {
    vi.mocked(checkPermission).mockResolvedValue(true);
    const links: GatedSidebarLink[] = [
      {
        key: "b",
        label: "B",
        icon: noopIcon,
        route: "b",
        permission: "email.whitelist.read",
        scope: "whitelist",
      },
    ];

    await resolveSidebarPermissions("tok", links);

    expect(checkPermission).toHaveBeenCalledWith("tok", "email.whitelist.read", {
      scope: "whitelist",
    });
  });

  it("fails closed (false) when a link's check rejects", async () => {
    vi.mocked(checkPermission).mockRejectedValueOnce(new Error("network"));
    const links: GatedSidebarLink[] = [
      { key: "a", label: "A", icon: noopIcon, route: "a", permission: "analytics.read" },
    ];

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: false });
  });
});
