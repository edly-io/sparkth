import { api, bearer, call } from "@/lib/api";
import type { PermissionCheckResponse, PermissionName } from "@/lib/permissions/types";

// Ask the backend whether the current user holds `permission` (default global scope).
// Returns the boolean answer; the endpoint is a UI-gating convenience, not a security boundary.
export async function checkPermission(
  token: string,
  permission: PermissionName,
  { scope, scopeObjectId }: { scope?: string; scopeObjectId?: string } = {},
): Promise<boolean> {
  const { allowed } = await call<PermissionCheckResponse>(() =>
    api.GET("/api/v1/permissions/can", {
      params: { query: { permission, scope, scope_object_id: scopeObjectId } },
      headers: bearer(token),
    }),
  );
  return allowed;
}
