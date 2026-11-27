/** Where the Roles tab lives. */
export const ROLES_PATH = "/dashboard/permissions/roles";

/** Where the Roles tab's view comparing the roles' permissions lives. */
export const ROLES_COMPARE_PATH = `${ROLES_PATH}/compare`;

/** Where the page of the role with `roleId` lives. */
export function getRolePath(roleId: number): string {
  return `${ROLES_PATH}/role?id=${roleId}`;
}
