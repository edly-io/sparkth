"use client";

import { useTranslations } from "next-intl";
import { BADGE_CLASS } from "@/core/permissions/components/ui/RoleBadges";
import { RolesViewSwitch } from "@/core/permissions/components/ui/RolesViewSwitch";

/**
 * The Roles tab's compare view: the switch back to the list and a badge saying the view changes
 * nothing. The comparison itself is not shown yet.
 */
export default function ComparePage() {
  const t = useTranslations("permissions.roles.compare");
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
      <RolesViewSwitch current="compare" />
      <span className={`${BADGE_CLASS} bg-surface-variant text-muted-foreground`}>
        {t("readOnly")}
      </span>
    </div>
  );
}
