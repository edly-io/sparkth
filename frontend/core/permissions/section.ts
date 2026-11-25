import type { PermissionCheckQuery } from "@/core/permissions/client";

/**
 * What opening the Access & permissions section takes: every one of these checks must pass. An
 * object-bearing scope without an object id asks about any of its objects.
 */
export const PERMISSIONS_SECTION_CHECKS: PermissionCheckQuery[] = [
  { permission: "permission.read", scope: "global" },
  { permission: "role.read", scope: "role" },
  { permission: "group.read", scope: "group" },
];
