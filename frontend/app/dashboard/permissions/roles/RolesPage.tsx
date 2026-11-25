"use client";

import { useTranslations } from "next-intl";
import { listRoles } from "@/core/permissions/client";
import { NamedEntryList } from "@/core/permissions/components/ui/NamedEntryList";

/** The Roles tab: the roles the signed-in user may read, by name and description. */
export default function RolesPage() {
  const t = useTranslations("permissions.roles");
  return (
    <NamedEntryList
      label={t("label")}
      load={listRoles}
      empty={t("empty")}
      loadFailed={t("loadFailed")}
    />
  );
}
