"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/core/permissions/components/ui/Badge";
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
      <Badge className="bg-surface-variant text-muted-foreground">{t("viewOnly")}</Badge>
    </div>
  );
}
