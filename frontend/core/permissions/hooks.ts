import { useEffect, useState } from "react";
import {
  checkPermission,
  checkPermissions,
  type PermissionQuestion,
} from "@/core/permissions/client";
import type { PermissionName } from "@/lib/permissions/names";

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
  { scope, scopeObjectId }: { scope: string; scopeObjectId?: string },
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

/**
 * Whether the signed-in user holds each of `questions`, answered by one request, for gating
 * several controls at once. Returns one `Access` per question, in order.
 *
 * Asks again only when the token or the questions' content changes, so an inline array is fine.
 * Goes back to `"checking"` on such a change, and fails closed, denying every question, when the
 * request errors.
 */
export function usePermissionChecks(
  token: string | null,
  questions: PermissionQuestion[],
): Access[] {
  // Keyed by content, not identity: a new array with the same questions must not ask again.
  const questionsKey = JSON.stringify(questions);
  const [answers, setAnswers] = useState<Access[]>(() => questions.map(() => "checking"));

  useEffect(() => {
    const asked: PermissionQuestion[] = JSON.parse(questionsKey);
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
  }, [token, questionsKey]);

  return answers;
}
