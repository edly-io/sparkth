"use client";

import type { ReactNode } from "react";
import { Lock, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatRoleName } from "@/core/permissions/roleDisplay";
import type { RoleResponse } from "@/core/permissions/types";

const BADGE = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium";

/**
 * One role in the Roles list: its name and description, a badge saying whether it ships with
 * Sparkth, is given to everyone or was made here, how many permissions it holds and who holds it.
 */
export function RoleCard({ role }: { role: RoleResponse }) {
  const t = useTranslations("permissions.roles");

  return (
    <article className="flex h-full flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm">
      <div>
        <h2 className="text-base font-semibold text-foreground">{formatRoleName(role.name)}</h2>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {role.is_builtin ? (
            <span
              className={`${BADGE} bg-neutral-200 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-100`}
            >
              <Lock className="h-3 w-3" aria-hidden="true" />
              {t("badges.builtin")}
            </span>
          ) : (
            <span className={`${BADGE} bg-primary-500/15 text-primary-600 dark:text-primary-400`}>
              {t("badges.custom")}
            </span>
          )}
          {role.is_default && (
            <span
              className={`${BADGE} bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300`}
            >
              <Zap className="h-3 w-3" aria-hidden="true" />
              {t("badges.default")}
            </span>
          )}
        </div>
      </div>
      {role.description && (
        <p className="flex-1 text-sm text-muted-foreground">{role.description}</p>
      )}
      <div className="mt-auto flex flex-wrap gap-x-6 gap-y-1 border-t border-border pt-3 text-[13px] text-muted-foreground">
        <span>{t.rich("permissionCount", { count: role.permissions.length, strong: bold })}</span>
        {bold(getHoldersText(role, t))}
      </div>
    </article>
  );
}

/** Shows footer text in bold and the darker colour: the permission count's figure and who holds the role. */
function bold(chunks: ReactNode) {
  return <strong className="font-semibold text-foreground">{chunks}</strong>;
}

/** Who holds the role: everyone for a role every account is given, else its groups and people. */
function getHoldersText(
  role: RoleResponse,
  t: ReturnType<typeof useTranslations<"permissions.roles">>,
): string {
  if (role.is_default) return t("everyone");
  const parts = [
    role.group_count > 0 ? t("groupCount", { count: role.group_count }) : null,
    role.user_count > 0 ? t("peopleCount", { count: role.user_count }) : null,
  ].filter((part) => part !== null);
  return parts.length > 0 ? parts.join(" · ") : t("notAssigned");
}
