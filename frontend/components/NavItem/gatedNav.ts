import type { ComponentType } from "react";
import { ChartColumn, Shield } from "lucide-react";
import { checkPermission, type PermissionName } from "@/lib/permissions";

export interface GatedNavItem {
  key: string; // stable id; also the navPermissions map key
  label: string;
  icon: ComponentType<{ className?: string }>;
  route: string; // href suffix: `${basePath}/${route}`
  activeKey?: string; // isActiveRoute() key; defaults to `route`
  permission: PermissionName;
  scope?: string; // omit for the global scope
}

export const GATED_NAV: GatedNavItem[] = [
  {
    key: "analytics",
    label: "Analytics",
    icon: ChartColumn,
    route: "analytics",
    permission: "analytics.read",
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
];

// Resolve every gated item's permission once, failing closed per item. Keyed by item.key.
export async function resolveNavPermissions(
  token: string,
  items: GatedNavItem[] = GATED_NAV,
): Promise<Record<string, boolean>> {
  const entries = await Promise.all(
    items.map(async (item) => {
      try {
        const allowed = await checkPermission(token, item.permission, { scope: item.scope });
        return [item.key, allowed] as const;
      } catch (error) {
        console.error(`Permission check failed for "${item.permission}":`, error);
        return [item.key, false] as const;
      }
    }),
  );
  return Object.fromEntries(entries);
}
