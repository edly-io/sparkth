"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/core/auth/hooks";
import { listPermissions, listRoles } from "@/core/permissions/client";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

/** What the compare view has loaded so far. */
export type RoleComparison =
  | { status: "loading" | "failed" }
  | { status: "loaded"; roles: RoleResponse[]; permissions: PermissionResponse[] };

/** Loads the roles and every permission together; fails if either does. */
export function useRoleComparison(): RoleComparison {
  const { token } = useAuth();
  const [comparison, setComparison] = useState<RoleComparison>({ status: "loading" });

  useEffect(() => {
    setComparison({ status: "loading" });
    if (!token) return;
    let active = true;
    Promise.all([listRoles(token), listPermissions(token)])
      .then(([roles, permissions]) => {
        if (active) setComparison({ status: "loaded", roles, permissions });
      })
      .catch((error: unknown) => {
        console.error("Loading the role comparison failed:", error);
        if (active) setComparison({ status: "failed" });
      });
    return () => {
      active = false;
    };
  }, [token]);

  return comparison;
}
