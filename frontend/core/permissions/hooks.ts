import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkPermissions,
  listPermissions,
  type PermissionCheckQuery,
} from "@/core/permissions/client";
import type { PermissionResponse } from "@/core/permissions/types";
import type { PermissionName } from "@/lib/permissions/names";

/** Where a permission check stands: still in flight, granted, or refused (including on error). */
export type Access = "checking" | "allowed" | "denied";

/**
 * Whether the signed-in user holds `permission`, for gating a page or panel, asked as a batch of
 * one. Goes back to `"checking"` whenever the token or check changes, and fails closed to
 * `"denied"` when the check errors.
 */
export function usePermissionCheck(
  token: string | null,
  permission: PermissionName,
  { scope, scopeObjectId }: { scope: string; scopeObjectId?: string },
): Access {
  const [access] = usePermissionChecks(token, [{ permission, scope, scopeObjectId }]);
  return access;
}

/**
 * Whether the signed-in user holds each of `checks`, answered by one request, for gating
 * several controls at once. Returns one `Access` per check, in order.
 *
 * Asks again only when the token or the checks' content changes, so an inline array is fine.
 * Goes back to `"checking"` on such a change, and fails closed, denying every check, when the
 * request errors.
 */
export function usePermissionChecks(
  token: string | null,
  checks: PermissionCheckQuery[],
): Access[] {
  // Keyed by content, not identity: a new array with the same checks must not ask again.
  const checksKey = JSON.stringify(checks);
  const [answers, setAnswers] = useState<Access[]>(() => checks.map(() => "checking"));

  useEffect(() => {
    const asked: PermissionCheckQuery[] = JSON.parse(checksKey);
    setAnswers(asked.map(() => "checking"));
    if (!token) return;
    let active = true;
    checkPermissions(token, asked)
      .then((allowed) => {
        if (active) setAnswers(allowed.map((granted) => (granted ? "allowed" : "denied")));
      })
      .catch((error: unknown) => {
        console.error("Permission checks failed:", error);
        if (active) setAnswers(asked.map(() => "denied"));
      });
    return () => {
      active = false;
    };
  }, [token, checksKey]);

  return answers;
}

/**
 * What the signed-in user may do with roles, answered by one request: create one, delete the role
 * `roleId` and change it, or delete roles in general when no role is named. Creating needs
 * `role.update` everywhere as well as `role.create`, since a new role can start with permissions.
 * Each is false until the answer arrives, and `canChange` stays false when no role is named.
 */
export function useRoleAccess(
  token: string | null,
  roleId?: number,
): { canCreate: boolean; canChange: boolean; canDelete: boolean } {
  const scopeObjectId = roleId === undefined ? undefined : String(roleId);
  const checks: PermissionCheckQuery[] = [
    { permission: "role.create", scope: "global" },
    { permission: "role.update", scope: "global" },
    { permission: "role.delete", scope: "role", scopeObjectId },
  ];
  if (roleId !== undefined) {
    checks.push({ permission: "role.update", scope: "role", scopeObjectId });
  }
  const [createAllowed, changeAllAllowed, deleteAllowed, changeAllowed = false] =
    usePermissionChecks(token, checks).map((access) => access === "allowed");
  return {
    canCreate: createAllowed && changeAllAllowed,
    canChange: changeAllowed,
    canDelete: deleteAllowed,
  };
}

/** Where the full permission list stands: not asked for yet, in flight, failed, or loaded. */
export type PermissionListState =
  | { status: "idle" | "loading" | "failed" }
  | { status: "loaded"; permissions: PermissionResponse[] };

/**
 * Every declared permission, loaded the first time `load` is called with a token; idle until then.
 * Later calls do nothing once the list is loading or loaded, so a caller can call `load` whenever it
 * needs the list; after a failure, the next call asks again.
 */
export function usePermissionList(token: string | null): {
  permissionList: PermissionListState;
  load: () => void;
} {
  const [permissionList, setPermissionList] = useState<PermissionListState>({ status: "idle" });
  // A ref, not the state: two calls before a re-render must still ask once.
  const requested = useRef(false);

  const load = useCallback(() => {
    if (requested.current || !token) return;
    requested.current = true;
    setPermissionList({ status: "loading" });
    listPermissions(token)
      .then((permissions) => setPermissionList({ status: "loaded", permissions }))
      .catch((error: unknown) => {
        console.error("Loading the permissions failed:", error);
        requested.current = false;
        setPermissionList({ status: "failed" });
      });
  }, [token]);

  return { permissionList, load };
}
