"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/core/auth/hooks";
import { Button } from "@/core/components/ui/Button";
import { createRole, deleteRole, listRoles } from "@/core/permissions/client";
import { usePermissionChecks } from "@/core/permissions/hooks";
import type { PermissionCheckQuery } from "@/core/permissions/client";
import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";
import { DeleteRoleDialog } from "@/core/permissions/components/ui/DeleteRoleDialog";
import type { RoleCreate, RoleResponse } from "@/core/permissions/types";
import { ListLoader } from "@/core/permissions/components/ui/ListLoader";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";

/**
 * What the page asks before showing its actions, read by position as create, update, delete.
 * Creating a role needs `role.update` too, since a new role can start with permissions.
 */
const ROLE_ACTION_CHECKS: PermissionCheckQuery[] = [
  { permission: "role.create", scope: "global" },
  { permission: "role.update", scope: "global" },
  { permission: "role.delete", scope: "role" },
];

/**
 * The Roles tab: a card for each role the signed-in user may read, under a switch between the list
 * and a permission comparison that is not available yet. Those who may create and change roles get a
 * Create role button, and those who may delete roles a Delete action on each custom role.
 */
export default function RolesPage() {
  const t = useTranslations("permissions.roles");
  const { token } = useAuth();
  const [createAccess, updateAccess, deleteAccess] = usePermissionChecks(token, ROLE_ACTION_CHECKS);
  const mayCreate = createAccess === "allowed" && updateAccess === "allowed";
  const mayDelete = deleteAccess === "allowed";
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<RoleResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const create = async (role: RoleCreate) => {
    if (!token) throw new Error("not signed in");
    await createRole(token, role);
    setReloadKey((key) => key + 1);
  };

  const confirmDelete = async (role: RoleResponse) => {
    if (!token) throw new Error("not signed in");
    await deleteRole(token, role.id);
    setDeleting(null);
    setReloadKey((key) => key + 1);
  };

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div
          role="group"
          aria-label={t("view.label")}
          className="inline-flex rounded-[10px] bg-surface-variant p-1"
        >
          <Link
            href="/dashboard/permissions/roles"
            aria-current="page"
            className="rounded-lg bg-card px-3.5 py-2 text-sm font-semibold text-foreground shadow-sm"
          >
            {t("view.list")}
          </Link>
          <button
            type="button"
            disabled
            className="rounded-lg px-3.5 py-2 text-sm font-medium text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("view.compare")}
          </button>
        </div>
        {mayCreate && (
          <Button variant="outline" size="sm" className="py-2" onClick={() => setCreating(true)}>
            <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
            {t("create.button")}
          </Button>
        )}
      </div>
      <CreateRoleDialog open={creating} onCreate={create} onClose={() => setCreating(false)} />
      {deleting && (
        <DeleteRoleDialog
          role={deleting}
          onConfirm={() => confirmDelete(deleting)}
          onClose={() => setDeleting(null)}
        />
      )}
      <ListLoader
        load={listRoles}
        empty={t("empty")}
        loadFailed={t("loadFailed")}
        reloadKey={reloadKey}
      >
        {(roles) => (
          <>
            <p className="mb-4 text-sm text-muted-foreground">{t("intro")}</p>
            <ul aria-label={t("label")} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {roles.map((role) => (
                <li key={role.id}>
                  <RoleCard
                    role={role}
                    onDelete={mayDelete && !role.is_builtin ? () => setDeleting(role) : undefined}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
      </ListLoader>
    </>
  );
}
