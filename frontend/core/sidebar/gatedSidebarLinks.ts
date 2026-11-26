import type { ComponentType } from "react";
import { ChartColumn, KeyRound, ScrollText, Shield } from "lucide-react";
import { checkPermissions, type PermissionCheckQuery } from "@/lib/permissions/client";
import { PERMISSIONS_SECTION_CHECKS } from "@/core/permissions/section";

/** A sidebar link shown only to users who pass every one of its permission checks. */
export interface GatedSidebarLink {
  key: string; // stable id; also the sidebarPermissions map key
  label: string;
  icon: ComponentType<{ className?: string }>;
  route: string; // href suffix: `${basePath}/${route}`
  activeKey?: string; // isActiveRoute() key; defaults to `route`
  checks: PermissionCheckQuery[];
}

/** The permission-gated sidebar links, in the order the sidebar shows them. */
export const GATED_SIDEBAR_LINKS: GatedSidebarLink[] = [
  {
    key: "analytics",
    label: "Analytics",
    icon: ChartColumn,
    route: "analytics",
    checks: [{ permission: "analytics.read", scope: "global" }],
  },
  {
    key: "permissions",
    label: "Access & permissions",
    icon: KeyRound,
    route: "permissions/roles",
    activeKey: "permissions",
    checks: PERMISSIONS_SECTION_CHECKS,
  },
  {
    key: "admin",
    label: "Admin",
    icon: Shield,
    route: "admin/whitelist",
    activeKey: "admin",
    checks: [{ permission: "email.whitelist.read", scope: "whitelist" }],
  },
  {
    key: "audit",
    label: "Audit log",
    icon: ScrollText,
    route: "audit",
    checks: [{ permission: "audit.read", scope: "global" }],
  },
];

/**
 * Asks every gated link's checks in one request and maps each link's key to whether all of its
 * checks passed. The request fails as a whole, so a failure denies every link.
 */
export async function resolveSidebarPermissions(
  token: string,
  links: GatedSidebarLink[] = GATED_SIDEBAR_LINKS,
): Promise<Record<string, boolean>> {
  let grants: boolean[];
  try {
    grants = await checkPermissions(
      token,
      links.flatMap(({ checks }) => checks),
    );
  } catch (error) {
    console.error("Sidebar permission checks failed:", error);
    return Object.fromEntries(links.map(({ key }) => [key, false]));
  }
  // The answers come back in the order asked: each link's run of checks, link after link.
  let start = 0;
  return Object.fromEntries(
    links.map(({ key, checks }) => {
      const answers = grants.slice(start, start + checks.length);
      start += checks.length;
      return [key, answers.every(Boolean)];
    }),
  );
}
