import type { PermissionCheckQuery } from "@/core/permissions/client";
import type { PermissionsTab } from "@/core/permissions/components/ui/PermissionsNav";

/**
 * What opening the Access & permissions section takes: every one of these checks must pass. An
 * object-bearing scope without an object id asks about any of its objects.
 */
export const PERMISSIONS_SECTION_CHECKS: PermissionCheckQuery[] = [
  { permission: "permission.read", scope: "global" },
  { permission: "role.read", scope: "role" },
  { permission: "group.read", scope: "group" },
];

/** The section's tabs, in the order the tab bar shows them. */
export const PERMISSIONS_TABS: readonly PermissionsTab[] = [
  { key: "roles", href: "/dashboard/permissions/roles" },
  { key: "groups", href: "/dashboard/permissions/groups" },
];
