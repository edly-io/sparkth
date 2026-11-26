import { TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import type { PermissionRisk } from "@/core/permissions/types";

/** The risks of a role or a permission as warning chips; nothing when there are none. */
export function RiskChips({ risks }: { risks: readonly PermissionRisk[] }) {
  const t = useTranslations("permissions.roles.risks");
  if (risks.length === 0) return null;
  return (
    <ul aria-label={t("label")} className="flex flex-wrap gap-1.5">
      {risks.map((risk) => (
        <li
          key={risk}
          className="inline-flex items-center gap-1 rounded-md border border-warning-100 bg-warning-50 px-2 py-0.5 text-xs font-medium text-warning-700 dark:border-warning-700/40 dark:bg-warning-700/15 dark:text-warning-500"
        >
          <TriangleAlert className="h-3 w-3" aria-hidden="true" />
          {t(risk)}
        </li>
      ))}
    </ul>
  );
}
