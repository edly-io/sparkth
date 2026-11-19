import { api, bearer, call } from "@/lib/api";
import type { PermissionCheckResponse, PermissionCheckResult } from "@/core/permissions/types";
import type { PermissionName } from "@/lib/permissions/names";

/** The scope a question without one is asked at. */
const GLOBAL_SCOPE = "global";

/** One "may the current user do this?" question: a permission, optionally at a scope and one of its objects. */
export interface PermissionQuestion {
  permission: PermissionName;
  scope?: string; // omit for the global scope
  scopeObjectId?: string; // omit at an object-bearing scope to ask about any of its objects
}

/**
 * Ask the backend whether the current user holds `permission` (default global scope).
 * Returns the boolean answer; the endpoint is a UI-gating convenience, not a security boundary.
 */
export async function checkPermission(
  token: string,
  permission: PermissionName,
  { scope, scopeObjectId }: { scope?: string; scopeObjectId?: string } = {},
): Promise<boolean> {
  const { allowed } = await call<PermissionCheckResponse>(() =>
    api.POST("/api/v1/permissions/can", {
      body: { permission, scope: scope ?? GLOBAL_SCOPE, scope_object_id: scopeObjectId },
      headers: bearer(token),
    }),
  );
  return allowed;
}

/**
 * Ask the backend about several permissions in one request. Returns one answer per question, in
 * the order asked. The request fails as a whole, so a caller treats a rejection as a denial of all.
 */
export async function checkPermissions(
  token: string,
  questions: PermissionQuestion[],
): Promise<boolean[]> {
  const results = await call<PermissionCheckResult[]>(() =>
    api.POST("/api/v1/permissions/can/batch", {
      body: questions.map(({ permission, scope, scopeObjectId }) => ({
        permission,
        scope: scope ?? GLOBAL_SCOPE,
        scope_object_id: scopeObjectId,
      })),
      headers: bearer(token),
    }),
  );
  return results.map(({ allowed }) => allowed);
}
