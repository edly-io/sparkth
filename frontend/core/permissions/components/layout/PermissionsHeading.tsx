"use client";

import { KeyRound } from "lucide-react";
import { useTranslations } from "next-intl";

/** The Access & permissions section's heading and what the section is for. */
export function PermissionsHeading() {
  const t = useTranslations("permissions");

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3">
        <KeyRound className="w-6 h-6 text-primary-500" aria-hidden="true" />
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{t("subtitle")}</p>
    </div>
  );
}
