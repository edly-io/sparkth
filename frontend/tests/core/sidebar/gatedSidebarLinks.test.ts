import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/core/permissions/client", () => ({ checkPermissions: vi.fn() }));

import { checkPermissions } from "@/core/permissions/client";
import { PERMISSIONS_SECTION_CHECKS } from "@/core/permissions/section";
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
  const link = (key: string) => GATED_SIDEBAR_LINKS.find((entry) => entry.key === key)!;

  it("declares the gated entries in sidebar order", () => {
    expect(GATED_SIDEBAR_LINKS.map((entry) => entry.key)).toEqual([
      "analytics",
      "permissions",
      "admin",
      "audit",
    ]);
  });

  it("gates analytics, admin and audit on one permission each", () => {
    expect(link("analytics").checks).toEqual([{ permission: "analytics.read", scope: "global" }]);
    expect(link("admin").checks).toEqual([
      { permission: "email.whitelist.read", scope: "whitelist" },
    ]);
    expect(link("admin").route).toBe("admin/whitelist");
    expect(link("admin").activeKey).toBe("admin");
    expect(link("audit").checks).toEqual([{ permission: "audit.read", scope: "global" }]);
  });

  it("gates Access & permissions on the section's checks and opens its first tab", () => {
    const permissions = link("permissions");
    expect(permissions.label).toBe("Access & permissions");
    expect(permissions.checks).toEqual(PERMISSIONS_SECTION_CHECKS);
    expect(permissions.route).toBe("permissions/roles");
    expect(permissions.activeKey).toBe("permissions");
  });
});

describe("resolveSidebarPermissions", () => {
  const links: GatedSidebarLink[] = [
    {
      key: "a",
      label: "A",
      icon: noopIcon,
      route: "a",
      checks: [{ permission: "analytics.read", scope: "global" }],
    },
    {
      key: "b",
      label: "B",
      icon: noopIcon,
      route: "b",
      checks: [
        { permission: "role.read", scope: "role" },
        { permission: "group.read", scope: "group" },
      ],
    },
    {
      key: "c",
      label: "C",
      icon: noopIcon,
      route: "c",
      checks: [{ permission: "email.whitelist.read", scope: "whitelist" }],
    },
  ];

  it("asks every link's checks in one request, in link order", async () => {
    vi.mocked(checkPermissions).mockResolvedValue([true, true, true, true]);

    await resolveSidebarPermissions("tok", links);

    expect(checkPermissions).toHaveBeenCalledTimes(1);
    expect(checkPermissions).toHaveBeenCalledWith("tok", [
      { permission: "analytics.read", scope: "global" },
      { permission: "role.read", scope: "role" },
      { permission: "group.read", scope: "group" },
      { permission: "email.whitelist.read", scope: "whitelist" },
    ]);
  });

  it("shows a link only when every one of its checks passes", async () => {
    vi.mocked(checkPermissions).mockResolvedValue([true, true, true, false]);

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: true, b: true, c: false });
  });

  it("hides a link when any one of its checks is refused", async () => {
    vi.mocked(checkPermissions).mockResolvedValue([true, true, false, true]);

    expect(await resolveSidebarPermissions("tok", links)).toEqual({ a: true, b: false, c: true });
  });

  it("fails closed (false) for every link when the request rejects", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(checkPermissions).mockRejectedValue(new Error("network"));

    expect(await resolveSidebarPermissions("tok", links)).toEqual({
      a: false,
      b: false,
      c: false,
    });
  });
});
