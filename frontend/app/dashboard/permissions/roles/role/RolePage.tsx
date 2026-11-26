"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/core/auth/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Button } from "@/core/components/ui/Button";
import { Spinner } from "@/core/components/ui/Spinner";
import { getRole, setRolePermissions } from "@/core/permissions/client";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import { RoleBadges } from "@/core/permissions/components/ui/RoleBadges";
import { RolePermissionList } from "@/core/permissions/components/ui/RolePermissionList";
import { usePermissionList } from "@/core/permissions/hooks";
import { ROLES_PATH } from "@/core/permissions/paths";
import { formatRoleName } from "@/core/permissions/roleDisplay";
import type { RoleResponse } from "@/core/permissions/types";

type SaveStatus = "idle" | "saving" | "saved" | "failed";

/** How long "Saved" shows after a save, in milliseconds. */
const SAVED_MESSAGE_MS = 3000;

/**
 * A loaded role: `checked` starts as every permission it holds, so one no longer declared is saved
 * back unchanged, and `saveStatus` says where saving the checked ones stands.
 */
type LoadedRole = {
  status: "loaded";
  role: RoleResponse;
  checked: ReadonlySet<string>;
  saveStatus: SaveStatus;
};

type RoleState = { status: "loading" | "missing" | "failed" } | LoadedRole;

/**
 * One role's page, for the role named by `?id=`: a breadcrumb back through Access & permissions and
 * Roles, then the role's name as the page heading with its badges, description and risks, and every
 * permission with the role's own checked. A custom role's permissions can be checked and unchecked,
 * and Save, enabled once they differ from the role's, saves them all at once and says so. Says so
 * too when there is no such role, it can't be loaded or saving fails.
 */
export default function RolePage() {
  const t = useTranslations("permissions.roles.detail");
  const tPermissions = useTranslations("permissions");
  const { token } = useAuth();
  const roleId = Number(useSearchParams()?.get("id"));
  const [state, setState] = useState<RoleState>({ status: "loading" });
  const { permissionList, load: loadPermissionList } = usePermissionList(token);

  useEffect(() => loadPermissionList(), [loadPermissionList]);

  const saveStatus = state.status === "loaded" ? state.saveStatus : "idle";
  useEffect(() => {
    if (saveStatus !== "saved") return;
    const timer = setTimeout(
      () =>
        setState((current) =>
          current.status === "loaded" && current.saveStatus === "saved"
            ? { ...current, saveStatus: "idle" }
            : current,
        ),
      SAVED_MESSAGE_MS,
    );
    return () => clearTimeout(timer);
  }, [saveStatus]);

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
        if (active) setState(getLoadedState(role, "idle"));
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

  const { role, checked } = state;
  const name = formatRoleName(role.name);
  const held = new Set(role.permissions);
  const changed =
    checked.size !== held.size || [...checked].some((permission) => !held.has(permission));

  // Applies `next` only while the same role is on show, so a save finishing after another role
  // was opened changes nothing.
  const updateShownRole = (next: (current: LoadedRole) => LoadedRole) =>
    setState((current) =>
      current.status === "loaded" && current.role.id === role.id ? next(current) : current,
    );

  const saveChecked = async () => {
    if (!token) return;
    setState({ ...state, saveStatus: "saving" });
    try {
      const savedRole = await setRolePermissions(token, role.id, [...checked]);
      updateShownRole(() => getLoadedState(savedRole, "saved"));
    } catch (error) {
      console.error("Saving the role's permissions failed:", error);
      updateShownRole((current) => ({ ...current, saveStatus: "failed" }));
    }
  };

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
          granted={checked}
          onChange={
            role.is_builtin || saveStatus === "saving"
              ? undefined
              : (next) => setState({ ...state, checked: next, saveStatus: "idle" })
          }
          actions={
            !role.is_builtin && (
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

/** A role just loaded or saved: every permission it holds checked, and `saveStatus` as given. */
function getLoadedState(role: RoleResponse, saveStatus: SaveStatus): LoadedRole {
  return { status: "loaded", role, checked: new Set(role.permissions), saveStatus };
}
