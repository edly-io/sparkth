import type { PermissionsTab } from "@/core/permissions/components/ui/PermissionsNav";
import { ROLES_PATH } from "@/core/permissions/paths";

/** The Access & permissions tabs, in the order the tab bar shows them. */
export const PERMISSIONS_TABS = [
  { key: "roles", href: ROLES_PATH },
  { key: "groups", href: "/dashboard/permissions/groups" },
] as const satisfies readonly PermissionsTab[];
