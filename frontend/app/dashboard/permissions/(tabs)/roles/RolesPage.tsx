"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/core/auth/hooks";
import { Button } from "@/core/components/ui/Button";
import { createRole, deleteRole, listRoles } from "@/core/permissions/client";
import { useRoleAccess } from "@/core/permissions/hooks";
import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";
import { DeleteRoleDialog } from "@/core/permissions/components/ui/DeleteRoleDialog";
import type { RoleCreate, RoleResponse } from "@/core/permissions/types";
import { ListLoader } from "@/core/permissions/components/ui/ListLoader";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";
import { RolesViewSwitch } from "@/core/permissions/components/ui/RolesViewSwitch";

/**
 * The Roles tab: a card for each role the signed-in user may read, under a switch between the list
 * and a permission comparison that is not available yet. Those who may create and change roles get a
 * Create role button, which can start the new role as a duplicate of a listed one, and those who may
 * delete roles a Delete action on each custom role.
 */
export default function RolesPage() {
  const t = useTranslations("permissions.roles");
  const { token } = useAuth();
  const { canCreate, canDelete } = useRoleAccess(token);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<RoleResponse | null>(null);
  const [loadedRoles, setLoadedRoles] = useState<RoleResponse[]>([]);
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
        <RolesViewSwitch current="list" />
        {canCreate && (
          <Button variant="outline" size="sm" className="py-2" onClick={() => setCreating(true)}>
            <Plus className="mr-1.5 h-4 w-4" aria-hidden="true" />
            {t("create.button")}
          </Button>
        )}
      </div>
      <CreateRoleDialog
        open={creating}
        roles={loadedRoles}
        onCreate={create}
        onClose={() => setCreating(false)}
      />
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
        onLoaded={setLoadedRoles}
      >
        {(roles) => (
          <>
            <p className="mb-4 text-sm text-muted-foreground">{t("intro")}</p>
            <ul aria-label={t("label")} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {roles.map((role) => (
                <li key={role.id}>
                  <RoleCard
                    role={role}
                    onDelete={canDelete && !role.is_builtin ? () => setDeleting(role) : undefined}
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
