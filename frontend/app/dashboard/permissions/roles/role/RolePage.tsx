"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight, Pencil } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRoleEditor } from "@/app/dashboard/permissions/roles/role/hooks";
import { useAuth } from "@/core/auth/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Button } from "@/core/components/ui/Button";
import { Spinner } from "@/core/components/ui/Spinner";
import { EditRoleDialog } from "@/core/permissions/components/ui/EditRoleDialog";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import { RoleBadges } from "@/core/permissions/components/ui/RoleBadges";
import { RolePermissionList } from "@/core/permissions/components/ui/RolePermissionList";
import { usePermissionCheck, usePermissionList } from "@/core/permissions/hooks";
import { ROLES_PATH } from "@/core/permissions/paths";
import { formatRoleName } from "@/core/permissions/roleDisplay";

/**
 * One role's page, for the role named by `?id=`: a breadcrumb back through Access & permissions and
 * Roles, then the role's name as the page heading with its badges, description and risks, and every
 * permission with the role's own checked. Those who may change a custom role can edit its name and
 * description, and check and uncheck its permissions, with Save, enabled once they differ from the
 * role's, saving them all at once and saying so. Says so too when there is no such role, it can't be
 * loaded or saving fails.
 */
export default function RolePage() {
  const t = useTranslations("permissions.roles.detail");
  const tPermissions = useTranslations("permissions");
  const { token } = useAuth();
  const idParam = Number(useSearchParams()?.get("id"));
  const roleId = Number.isInteger(idParam) && idParam > 0 ? idParam : null;
  const canChangeRole =
    usePermissionCheck(roleId === null ? null : token, "role.update", {
      scope: "role",
      scopeObjectId: String(roleId),
    }) === "allowed";
  const { state, changed, setChecked, saveChecked, saveDetails } = useRoleEditor(roleId);
  const [editing, setEditing] = useState(false);
  const { permissionList, load: loadPermissionList } = usePermissionList(token);

  useEffect(() => loadPermissionList(), [loadPermissionList]);

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

  const { role, checked, saveStatus } = state;
  const name = formatRoleName(role.name);
  const canEdit = canChangeRole && !role.is_builtin;

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
          {!role.is_builtin && (
            <Button
              variant="outline"
              size="sm"
              className="ml-auto px-2.5 py-1 text-xs"
              onClick={() => setEditing(true)}
            >
              <Pencil className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              {tPermissions("roles.edit.button")}
            </Button>
          )}
        </div>
        {role.description && <p className="text-sm text-muted-foreground">{role.description}</p>}
        <RiskChips risks={role.risks} />
      </header>
      <EditRoleDialog
        open={editing}
        role={role}
        onSave={saveDetails}
        onClose={() => setEditing(false)}
      />
      {permissionList.status === "loading" && (
        <div
          role="status"
          aria-label={t("permissionsLoading")}
          className="flex justify-center py-8"
        >
          <Spinner size="md" />
        </div>
      )}
      {permissionList.status === "failed" && (
        <Alert severity="error">{t("permissionsFailed")}</Alert>
      )}
      {permissionList.status === "loaded" && (
        <RolePermissionList
          permissions={permissionList.permissions}
          checked={checked}
          onChange={!canEdit || saveStatus === "saving" ? undefined : setChecked}
          actions={
            canEdit && (
              <>
                {saveStatus === "failed" && (
                  <p role="alert" className="text-sm text-error-600">
                    {t("saveFailed")}
                  </p>
                )}
                {saveStatus === "saved" && (
                  <p role="status" className="text-sm text-success-700 dark:text-success-300">
                    {t("saved")}
                  </p>
                )}
                <Button
                  size="sm"
                  loading={saveStatus === "saving"}
                  disabled={!changed}
                  onClick={saveChecked}
                >
                  {t("save")}
                </Button>
              </>
            )
          }
        />
      )}
    </div>
  );
}
