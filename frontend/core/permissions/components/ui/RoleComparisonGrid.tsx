"use client";

import { useId } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { GrantStatusIcon } from "@/core/permissions/components/ui/GrantStatusIcon";
import { RiskChips } from "@/core/permissions/components/ui/RiskChips";
import { RoleTypeBadge } from "@/core/permissions/components/ui/RoleBadges";
import { getRolePath } from "@/core/permissions/paths";
import { formatRoleName } from "@/core/permissions/roleDisplay";
import type { PermissionResponse, RoleResponse } from "@/core/permissions/types";

/** The permission column's width, narrower on small screens, as a CSS variable the table reads. */
const PERMISSION_COLUMN_WIDTH = "[--permission-column:200px] sm:[--permission-column:320px]";
const ROLE_COLUMN_WIDTH = 112;

/**
 * A table of permissions (rows) by roles (columns), named `caption`. Each cell says whether the
 * role is granted the permission. Columns have fixed widths; text that does not fit is cut short.
 */
export function RoleComparisonGrid({
  caption,
  permissions,
  roles,
}: {
  caption: string;
  permissions: PermissionResponse[];
  roles: RoleResponse[];
}) {
  const t = useTranslations("permissions.roles.compare");
  const columns = roles.map((role) => ({ role, granted: new Set(role.permissions) }));
  const grantedToSomeRole = new Set(roles.flatMap((role) => role.permissions));
  const labelIdPrefix = useId();

  return (
    <div className="w-fit max-w-full overflow-x-auto rounded-xl border border-border bg-card">
      <table
        className={`${PERMISSION_COLUMN_WIDTH} table-fixed border-separate border-spacing-0 text-sm`}
        style={{ width: `calc(var(--permission-column) + ${roles.length * ROLE_COLUMN_WIDTH}px)` }}
      >
        <caption className="sr-only">{caption}</caption>
        <colgroup>
          <col style={{ width: "var(--permission-column)" }} />
          {roles.map((role) => (
            <col key={role.id} style={{ width: ROLE_COLUMN_WIDTH }} />
          ))}
        </colgroup>
        <thead>
          <tr className="bg-surface-variant text-left">
            <th
              scope="col"
              className="sticky left-0 border-r border-border bg-surface-variant px-4 py-3 font-semibold text-foreground"
            >
              {t("permission")}
            </th>
            {columns.map(({ role }) => (
              <th key={role.id} scope="col" className="px-4 py-3">
                <div className="flex flex-col items-center gap-1">
                  <Link
                    href={getRolePath(role.id)}
                    className="block max-w-full truncate font-semibold text-foreground hover:underline"
                  >
                    {formatRoleName(role.name)}
                  </Link>
                  <RoleTypeBadge role={role} />
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {permissions.map(({ name, label, risks }) => (
            <tr key={name}>
              <th
                scope="row"
                aria-labelledby={`${labelIdPrefix}-${name}`}
                className="sticky left-0 space-y-1 border-r border-t border-border bg-card px-4 py-3 text-left font-normal"
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span
                    id={`${labelIdPrefix}-${name}`}
                    title={label}
                    className="max-w-full truncate font-medium text-foreground"
                  >
                    {label}
                  </span>
                  <RiskChips risks={risks} />
                </div>
                <code title={name} className="block truncate text-xs text-muted-foreground">
                  {name}
                </code>
                {!grantedToSomeRole.has(name) && (
                  <p className="text-xs text-muted-foreground">{t("noRole")}</p>
                )}
              </th>
              {columns.map(({ role, granted }) => (
                <td key={role.id} className="border-t border-border px-4 py-3">
                  <div className="flex justify-center">
                    <GrantStatusIcon granted={granted.has(name)} />
                    <span className="sr-only">
                      {granted.has(name) ? t("granted") : t("notGranted")}
                    </span>
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
