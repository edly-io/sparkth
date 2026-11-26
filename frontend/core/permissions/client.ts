import { api, bearer, call } from "@/lib/api";
import type { GroupResponse, RoleCreate, RoleResponse } from "@/core/permissions/types";

/** The roles the signed-in user may read, with each one's permissions. */
export async function listRoles(token: string): Promise<RoleResponse[]> {
  return call<RoleResponse[]>(() =>
    api.GET("/api/v1/permissions/roles", { headers: bearer(token) }),
  );
}

/** The groups the signed-in user may read. */
export async function listGroups(token: string): Promise<GroupResponse[]> {
  return call<GroupResponse[]>(() =>
    api.GET("/api/v1/permissions/groups", { headers: bearer(token) }),
  );
}

/** Creates a role with a name and an optional description, holding no permissions yet. */
export async function createRole(token: string, role: RoleCreate): Promise<RoleResponse> {
  return call<RoleResponse>(() =>
    api.POST("/api/v1/permissions/roles", { body: role, headers: bearer(token) }),
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
