"use client";

import { Eye } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  useRoleComparison,
  type RoleComparison,
} from "@/app/dashboard/permissions/(tabs)/roles/compare/hooks";
import { Alert } from "@/core/components/ui/Alert";
import { Select } from "@/core/components/ui/Select";
import { Spinner } from "@/core/components/ui/Spinner";
import { Badge } from "@/core/permissions/components/ui/Badge";
import { GrantStatusIcon } from "@/core/permissions/components/ui/GrantStatusIcon";
import { RoleComparisonGrid } from "@/core/permissions/components/ui/RoleComparisonGrid";
import { RolesViewSwitch } from "@/core/permissions/components/ui/RolesViewSwitch";
import { groupByCategory } from "@/core/permissions/permissionList";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

/** The Roles tab's compare view: the roles' permissions side by side, to look at only. */
export default function ComparePage() {
  const t = useTranslations("permissions.roles.compare");
  const comparison = useRoleComparison();
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <RolesViewSwitch current="compare" />
        <div className="flex flex-wrap items-center gap-4">
          <Badge className="bg-surface-variant text-muted-foreground">
            <Eye className="h-3 w-3" aria-hidden="true" />
            {t("viewOnly")}
          </Badge>
          {comparison.status === "loaded" && (
            <ul
              aria-label={t("legend")}
              className="flex items-center gap-4 text-sm text-muted-foreground"
            >
              <li className="flex items-center gap-1.5">
                <GrantStatusIcon granted />
                {t("granted")}
              </li>
              <li className="flex items-center gap-1.5">
                <GrantStatusIcon granted={false} />
                {t("notGranted")}
              </li>
            </ul>
          )}
        </div>
      </div>
      <Comparison comparison={comparison} />
    </>
  );
}

/** The comparison once loaded; a spinner or a message until then. */
function Comparison({ comparison }: { comparison: RoleComparison }) {
  const t = useTranslations("permissions.roles.compare");
  const tRoles = useTranslations("permissions.roles");
  switch (comparison.status) {
    case "loading":
      return (
        <div role="status" aria-label={t("loading")} className="flex justify-center py-24">
          <Spinner />
        </div>
      );
    case "failed":
      return <Alert severity="error">{t("loadFailed")}</Alert>;
  }
  const { roles, permissions } = comparison;
  if (roles.length === 0) return <p className="text-sm text-muted-foreground">{tRoles("empty")}</p>;
  if (permissions.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("noPermissions")}</p>;
  }
  return <ComparisonByCategory roles={roles} permissions={permissions} />;
}

/** The roles compared over one category of permissions at a time, chosen from a dropdown. */
function ComparisonByCategory({
  roles,
  permissions,
}: {
  roles: RoleResponse[];
  permissions: PermissionResponse[];
}) {
  const t = useTranslations("permissions.roles.compare");
  const permissionsByCategory = groupByCategory(permissions);
  const [firstCategory] = permissionsByCategory.keys();
  const [selectedCategory, setSelectedCategory] = useState(firstCategory);
  const shownPermissions = permissionsByCategory.get(selectedCategory);
  if (!shownPermissions)
    throw new Error(`The chosen category ${selectedCategory} is not among the options`);
  return (
    <div className="space-y-4">
      <div className="max-w-sm">
        <Select
          label={t("showFor")}
          value={selectedCategory}
          onChange={(event) => setSelectedCategory(event.target.value)}
          options={[...permissionsByCategory].map(([category, categoryPermissions]) => ({
            value: category,
            label: t("categoryOption", { category, count: categoryPermissions.length }),
          }))}
          className="border py-1.5 pl-3 text-sm"
        />
      </div>
      <RoleComparisonGrid caption={selectedCategory} permissions={shownPermissions} roles={roles} />
      <p className="text-sm text-muted-foreground">{t("note")}</p>
    </div>
  );
}
