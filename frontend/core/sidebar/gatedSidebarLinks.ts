import type { ComponentType } from "react";
import { ChartColumn, ScrollText, Shield } from "lucide-react";
import { checkPermission } from "@/core/permissions/client";
import type { PermissionName } from "@/lib/permissions/names";

/** A sidebar link shown only to users who hold its permission. */
export interface GatedSidebarLink {
  key: string; // stable id; also the sidebarPermissions map key
  label: string;
  icon: ComponentType<{ className?: string }>;
  route: string; // href suffix: `${basePath}/${route}`
  activeKey?: string; // isActiveRoute() key; defaults to `route`
  permission: PermissionName;
  scope?: string;
}

/** The permission-gated sidebar links, in the order the sidebar shows them. */
export const GATED_SIDEBAR_LINKS: GatedSidebarLink[] = [
  {
    key: "analytics",
    label: "Analytics",
    icon: ChartColumn,
    route: "analytics",
    permission: "analytics.read",
    scope: "global",
  },
  {
    key: "admin",
    label: "Admin",
    icon: Shield,
    route: "admin/whitelist",
    activeKey: "admin",
    permission: "email.whitelist.read",
    scope: "whitelist",
  },
  {
    key: "audit",
    label: "Audit log",
    icon: ScrollText,
    route: "audit",
    permission: "audit.read",
    scope: "global",
  },
];

/** Checks each gated link's permission once, failing closed per link, and maps each link's key to the result. */
export async function resolveSidebarPermissions(
  token: string,
  links: GatedSidebarLink[] = GATED_SIDEBAR_LINKS,
): Promise<Record<string, boolean>> {
  const entries = await Promise.all(
    links.map(async (link) => {
      try {
        const allowed = await checkPermission(token, link.permission, { scope: link.scope });
        return [link.key, allowed] as const;
      } catch (error) {
        console.error(`Permission check failed for "${link.permission}":`, error);
        return [link.key, false] as const;
      }
    }),
  );
  return Object.fromEntries(entries);
}
