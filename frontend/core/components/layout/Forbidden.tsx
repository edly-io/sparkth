"use client";

import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { BackToDashboardLink } from "@/core/components/layout/BackToDashboardLink";

// Rendered in place of content the user lacks permission for. It names no permission, so
// nothing about the access model is disclosed. A static export can't send a 403 status, so
// this is the client-side equivalent.
export function Forbidden() {
  const t = useTranslations("forbidden");

  return (
    <div className="bg-card rounded-lg border border-border p-12 text-center">
      <ShieldAlert className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" aria-hidden="true" />
      <h2 className="text-xl font-semibold text-foreground">{t("title")}</h2>
      <p className="mt-2 text-muted-foreground">{t("message")}</p>
      <div className="mt-6">
        <BackToDashboardLink />
      </div>
    </div>
  );
}
