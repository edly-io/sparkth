"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { listRoles } from "@/core/permissions/client";
import { ListLoader } from "@/core/permissions/components/ui/ListLoader";
import { RoleCard } from "@/core/permissions/components/ui/RoleCard";

/**
 * The Roles tab: a card for each role the signed-in user may read, under a switch between the list
 * and a permission comparison that is not available yet.
 */
export default function RolesPage() {
  const t = useTranslations("permissions.roles");
  return (
    <>
      <div
        role="group"
        aria-label={t("view.label")}
        className="mb-4 inline-flex rounded-[10px] bg-surface-variant p-1"
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
      <ListLoader load={listRoles} empty={t("empty")} loadFailed={t("loadFailed")}>
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
