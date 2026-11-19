import type { ComponentType } from "react";
import { ChartColumn, ScrollText, Shield } from "lucide-react";
import { checkPermissions } from "@/core/permissions/client";
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

/**
 * Checks every gated link's permission in one request and maps each link's key to its answer.
 * The request fails as a whole, so a failure denies every link.
 */
export async function resolveSidebarPermissions(
  token: string,
  links: GatedSidebarLink[] = GATED_SIDEBAR_LINKS,
): Promise<Record<string, boolean>> {
  let answers: boolean[];
  try {
    answers = await checkPermissions(
      token,
      links.map(({ permission, scope }) => ({ permission, scope })),
    );
  } catch (error) {
    console.error("Sidebar permission checks failed:", error);
    answers = links.map(() => false);
  }
  return Object.fromEntries(links.map((link, index) => [link.key, answers[index]]));
}
