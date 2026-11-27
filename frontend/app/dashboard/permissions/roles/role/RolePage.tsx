"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/core/auth/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Spinner } from "@/core/components/ui/Spinner";
import { getRole } from "@/core/permissions/client";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import { RoleBadges } from "@/core/permissions/components/ui/RoleBadges";
import { RolePermissionList } from "@/core/permissions/components/ui/RolePermissionList";
import { usePermissionList } from "@/core/permissions/hooks";
import { ROLES_PATH } from "@/core/permissions/paths";
import { formatRoleName } from "@/core/permissions/roleDisplay";
import type { RoleResponse } from "@/core/permissions/types";

type RoleState =
  | { status: "loading" | "missing" | "failed" }
  | { status: "loaded"; role: RoleResponse };

/**
 * One role's page, for the role named by `?id=`: a breadcrumb back through Access & permissions and
 * Roles, then the role's name as the page heading with its badges, description and risks, and every
 * permission with the role's own ticked. Says so when there is no such role or it can't be loaded.
 */
export default function RolePage() {
  const t = useTranslations("permissions.roles.detail");
  const tPermissions = useTranslations("permissions");
  const { token } = useAuth();
  const roleId = Number(useSearchParams()?.get("id"));
  const [state, setState] = useState<RoleState>({ status: "loading" });
  const { permissionList, load: loadPermissionList } = usePermissionList(token);

  useEffect(() => loadPermissionList(), [loadPermissionList]);

  useEffect(() => {
    if (!Number.isInteger(roleId) || roleId <= 0) {
      setState({ status: "missing" });
      return;
    }
    setState({ status: "loading" });
    if (!token) return;
    let active = true;
    getRole(token, roleId)
      .then((role) => {
        if (active) setState({ status: "loaded", role });
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiRequestError && error.status === 404) {
          setState({ status: "missing" });
          return;
        }
        console.error("Loading the role failed:", error);
        setState({ status: "failed" });
      });
    return () => {
      active = false;
    };
  }, [token, roleId]);

  switch (state.status) {
    case "missing":
      return <Alert severity="warning">{t("notFound")}</Alert>;
    case "failed":
      return <Alert severity="error">{t("loadFailed")}</Alert>;
    case "loading":
      return (
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      );
  }

  const { role } = state;
  const name = formatRoleName(role.name);
  return (
    <div className="space-y-6">
      <nav aria-label={t("breadcrumb")}>
        <ol className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <li>{tPermissions("title")}</li>
          <li aria-hidden="true">
            <ChevronRight className="h-4 w-4" />
          </li>
          <li>
            <Link href={ROLES_PATH} className="hover:text-foreground">
              {tPermissions("nav.roles")}
            </Link>
          </li>
          <li aria-hidden="true">
            <ChevronRight className="h-4 w-4" />
          </li>
          <li aria-current="page" className="font-medium text-foreground">
            {name}
          </li>
        </ol>
      </nav>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{name}</h1>
          <RoleBadges role={role} />
        </div>
        {role.description && <p className="text-sm text-muted-foreground">{role.description}</p>}
        <RiskChips risks={role.risks} />
      </header>
      {permissionList.status === "failed" && (
        <Alert severity="error">{t("permissionsFailed")}</Alert>
      )}
      {permissionList.status === "loaded" && (
        <RolePermissionList
          permissions={permissionList.permissions}
          granted={new Set(role.permissions)}
        />
      )}
    </div>
  );
}
