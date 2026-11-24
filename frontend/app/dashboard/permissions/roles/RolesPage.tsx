"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAuth } from "@/core/auth/hooks";
import { Button } from "@/core/components/ui/Button";
import { createRole, listRoles } from "@/core/permissions/client";
import { usePermissionCheck } from "@/core/permissions/hooks";
import { CreateRoleDialog } from "@/core/permissions/components/ui/CreateRoleDialog";
import type { RoleCreate } from "@/core/permissions/types";
import { ListLoader } from "@/core/permissions/components/ui/ListLoader";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";

/**
 * The Roles tab: a card for each role the signed-in user may read, under a switch between the list
 * and a permission comparison that is not available yet, and a Create role button for those who may
 * create roles.
 */
export default function RolesPage() {
  const t = useTranslations("permissions.roles");
  const { token } = useAuth();
  const mayCreate = usePermissionCheck(token, "role.create", { scope: "global" }) === "allowed";
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const create = async (role: RoleCreate) => {
    if (!token) throw new Error("not signed in");
    await createRole(token, role);
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
                  <RoleCard role={role} />
                </li>
              ))}
            </ul>
          </>
        )}
      </ListLoader>
    </>
  );
}
