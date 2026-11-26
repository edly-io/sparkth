import type { useTranslations } from "next-intl";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

/**
 * A role's name as people read it: each run of underscores becomes a space and the first letter is
 * capitalised, so `sparkth_user` reads "Sparkth user".
 */
export function formatRoleName(name: string): string {
  const spaced = name.replace(/_+/g, " ").trim();
  return spaced.charAt(0).toLocaleUpperCase() + spaced.slice(1);
}

/**
 * The groups and people that hold `role` directly, as counted phrases ("2 groups", "1 person"), groups
 * first; empty when nobody does.
 */
export function getRoleHolders(
  role: RoleResponse,
  t: ReturnType<typeof useTranslations<"permissions.roles">>,
): string[] {
  return [
    role.group_count > 0 ? t("groupCount", { count: role.group_count }) : null,
    role.user_count > 0 ? t("peopleCount", { count: role.user_count }) : null,
  ].filter((part) => part !== null);
}

/** The ones of `permissions` that are still declared in `declared`, in the order given. */
export function getDeclaredPermissions(
  permissions: string[],
  declared: PermissionResponse[],
): string[] {
  const declaredNames = new Set(declared.map((permission) => permission.name));
  return permissions.filter((permission) => declaredNames.has(permission));
}
