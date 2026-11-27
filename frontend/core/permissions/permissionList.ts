import type { PermissionResponse } from "@/core/permissions/types";

/** `permissions` by category, with the categories and each one's permissions in the order given. */
export function groupByCategory(
  permissions: PermissionResponse[],
): Map<string, PermissionResponse[]> {
  const byCategory = new Map<string, PermissionResponse[]>();
  for (const permission of permissions) {
    const categoryPermissions = byCategory.get(permission.category);
    if (categoryPermissions) categoryPermissions.push(permission);
    else byCategory.set(permission.category, [permission]);
  }
  return byCategory;
}

/**
 * The ones of `permissions` whose label, category or internal name contains `search`, whatever the
 * case; all of them when `search` is blank.
 */
export function filterPermissions(
  permissions: PermissionResponse[],
  search: string,
): PermissionResponse[] {
  const query = search.trim().toLocaleLowerCase();
  return permissions.filter(({ name, label, category }) =>
    [name, label, category].some((text) => text.toLocaleLowerCase().includes(query)),
  );
}
