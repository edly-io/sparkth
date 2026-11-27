import { Lock, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import type { RoleResponse } from "@/core/permissions/types";

/** The shape every badge in the permissions pages shares; each adds its own colours. */
export const BADGE_CLASS =
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium";

/**
 * Badges saying whether a role ships with Sparkth (Built-in) or was made here (Custom), and whether
 * every account is given it (Automatic).
 */
export function RoleBadges({ role }: { role: Pick<RoleResponse, "is_builtin" | "is_default"> }) {
  const t = useTranslations("permissions.roles.badges");
  return (
    <div className="flex flex-wrap gap-1.5">
      {role.is_builtin ? (
        <span
          className={`${BADGE_CLASS} bg-neutral-200 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-100`}
        >
          <Lock className="h-3 w-3" aria-hidden="true" />
          {t("builtin")}
        </span>
      ) : (
        <span className={`${BADGE_CLASS} bg-primary-500/15 text-primary-600 dark:text-primary-400`}>
          {t("custom")}
        </span>
      )}
      {role.is_default && (
        <span
          className={`${BADGE_CLASS} bg-secondary-50 text-secondary-700 dark:bg-secondary-900/30 dark:text-secondary-300`}
        >
          <Zap className="h-3 w-3" aria-hidden="true" />
          {t("default")}
        </span>
      )}
    </div>
  );
}
