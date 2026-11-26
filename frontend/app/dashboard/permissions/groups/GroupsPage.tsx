"use client";

import { useTranslations } from "next-intl";
import { listGroups } from "@/core/permissions/client";
import { NamedEntryList } from "@/core/permissions/components/ui/NamedEntryList";

/** The Groups tab: the groups the signed-in user may read, by name and description. */
export default function GroupsPage() {
  const t = useTranslations("permissions.groups");
  return (
    <NamedEntryList
      label={t("label")}
      load={listGroups}
      empty={t("empty")}
      loadFailed={t("loadFailed")}
    />
  );
}
