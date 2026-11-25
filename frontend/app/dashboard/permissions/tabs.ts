import type { PermissionsTab } from "@/core/permissions/components/ui/PermissionsNav";

/** The Access & permissions tabs, in the order the tab bar shows them. */
export const PERMISSIONS_TABS = [
  { key: "roles", href: "/dashboard/permissions/roles" },
  { key: "groups", href: "/dashboard/permissions/groups" },
] as const satisfies readonly PermissionsTab[];
