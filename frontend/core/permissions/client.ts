import { api, bearer, call } from "@/lib/api";
import type {
  GroupResponse,
  PermissionCheckResult,
  PermissionResponse,
  RoleCreate,
  RoleResponse,
  RoleUpdate,
} from "@/core/permissions/types";
import type { PermissionName } from "@/lib/permissions/names";

/** One permission check: a permission at a scope, optionally at one of its objects. */
export interface PermissionCheckQuery {
  permission: PermissionName;
  scope: string; // e.g. "global"
  scopeObjectId?: string; // omit at an object-bearing scope to ask about any of its objects
}

/**
 * Ask the backend about several permissions in one request. Returns one answer per check, in
 * the order asked. The request fails as a whole, so a caller treats a rejection as a denial of all.
 */
export async function checkPermissions(
  token: string,
  checks: PermissionCheckQuery[],
): Promise<boolean[]> {
  const results = await call<PermissionCheckResult[]>(() =>
    api.POST("/api/v1/permissions/can/batch", {
      body: checks.map(({ permission, scope, scopeObjectId }) => ({
        permission,
        scope,
        scope_object_id: scopeObjectId,
      })),
      headers: bearer(token),
    }),
  );
  return results.map(({ allowed }) => allowed);
}

/** The roles the signed-in user may read, with each one's permissions. */
export async function listRoles(token: string): Promise<RoleResponse[]> {
  return call<RoleResponse[]>(() =>
    api.GET("/api/v1/permissions/roles", { headers: bearer(token) }),
  );
}

/** One role, with its permissions, how many hold it and its risks. */
export async function getRole(token: string, roleId: number): Promise<RoleResponse> {
  return call<RoleResponse>(() =>
    api.GET("/api/v1/permissions/roles/{role_id}", {
      params: { path: { role_id: roleId } },
      headers: bearer(token),
    }),
  );
}

/** The groups the signed-in user may read. */
export async function listGroups(token: string): Promise<GroupResponse[]> {
  return call<GroupResponse[]>(() =>
    api.GET("/api/v1/permissions/groups", { headers: bearer(token) }),
  );
}

/** Creates a role with a name, an optional description and the permissions it starts with, if any. */
export async function createRole(token: string, role: RoleCreate): Promise<RoleResponse> {
  return call<RoleResponse>(() =>
    api.POST("/api/v1/permissions/roles", { body: role, headers: bearer(token) }),
  );
}

/** Every permission Sparkth and its plugins declare, with its label, description, category and risks. */
export async function listPermissions(token: string): Promise<PermissionResponse[]> {
  return call<PermissionResponse[]>(() =>
    api.GET("/api/v1/permissions", { headers: bearer(token) }),
  );
}

/** Makes the role grant exactly `permissions`, granting what it lacks and revoking the rest. */
export async function setRolePermissions(
  token: string,
  roleId: number,
  permissions: string[],
): Promise<RoleResponse> {
  return call<RoleResponse>(() =>
    api.PUT("/api/v1/permissions/roles/{role_id}/permissions", {
      params: { path: { role_id: roleId } },
      body: { permissions },
      headers: bearer(token),
    }),
  );
}

/** Changes a role's name, its description or both; a field left out of `details` stays as it is. */
export async function updateRoleDetails(
  token: string,
  roleId: number,
  details: RoleUpdate,
): Promise<RoleResponse> {
  return call<RoleResponse>(() =>
    api.PATCH("/api/v1/permissions/roles/{role_id}", {
      params: { path: { role_id: roleId } },
      body: details,
      headers: bearer(token),
    }),
  );
}

/** Deletes a role, taking it away from everyone who holds it. */
export async function deleteRole(token: string, roleId: number): Promise<void> {
  await call(() =>
    api.DELETE("/api/v1/permissions/roles/{role_id}", {
      params: { path: { role_id: roleId } },
      headers: bearer(token),
    }),
  );
}
