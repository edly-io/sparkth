import { useEffect, useState } from "react";
import { checkPermission } from "@/lib/permissions/client";
import type { PermissionName } from "@/lib/permissions/types";

/** Where a permission check stands: still in flight, granted, or refused (including on error). */
export type Access = "checking" | "allowed" | "denied";

/**
 * Whether the signed-in user holds `permission`, for gating a page or panel.
 *
 * Goes back to `"checking"` whenever the token or permission changes, so a re-login never
 * briefly shows the previous user's answer, and fails closed to `"denied"` when the check errors.
 */
export function usePermissionCheck(
  token: string | null,
  permission: PermissionName,
  { scope, scopeObjectId }: { scope?: string; scopeObjectId?: string } = {},
): Access {
  const [access, setAccess] = useState<Access>("checking");

  useEffect(() => {
    setAccess("checking");
    if (!token) return;
    let active = true;
    checkPermission(token, permission, { scope, scopeObjectId })
      .then((allowed) => {
        if (active) setAccess(allowed ? "allowed" : "denied");
      })
      .catch((error: unknown) => {
        console.error(`Permission check for ${permission} failed:`, error);
        if (active) setAccess("denied");
      });
    return () => {
      active = false;
    };
  }, [token, permission, scope, scopeObjectId]);

  return access;
}
