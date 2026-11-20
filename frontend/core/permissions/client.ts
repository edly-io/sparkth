import { api, bearer, call } from "@/lib/api";
import type { PermissionCheckResult } from "@/core/permissions/types";
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
