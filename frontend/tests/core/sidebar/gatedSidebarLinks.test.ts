import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/core/permissions/client", () => ({ checkPermissions: vi.fn() }));

import { checkPermissions } from "@/core/permissions/client";
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
    expect(analytics.scope).toBe("global");
    expect(admin.permission).toBe("email.whitelist.read");
    expect(admin.scope).toBe("whitelist");
    expect(admin.route).toBe("admin/whitelist");
    expect(admin.activeKey).toBe("admin");
    const audit = GATED_SIDEBAR_LINKS.find((link) => link.key === "audit")!;
    expect(audit.permission).toBe("audit.read");
    expect(audit.scope).toBe("global");
    expect(audit.route).toBe("audit");
  });
});

describe("resolveSidebarPermissions", () => {
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

  it("asks every link's permission and scope in one request", async () => {
    vi.mocked(checkPermissions).mockResolvedValue([true, true]);

    await resolveSidebarPermissions("tok", links);

    expect(checkPermissions).toHaveBeenCalledTimes(1);
    expect(checkPermissions).toHaveBeenCalledWith("tok", [
      { permission: "analytics.read", scope: undefined },
      { permission: "email.whitelist.read", scope: "whitelist" },
    ]);
  });

  it("returns a map keyed by link key with each answer", async () => {
    vi.mocked(checkPermissions).mockResolvedValue([true, false]);

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: true, b: false });
  });

  it("fails closed (false) for every link when the request rejects", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(checkPermissions).mockRejectedValue(new Error("network"));

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: false, b: false });
  });
});
