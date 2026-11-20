"use client";

import { KeyRound } from "lucide-react";
import { useTranslations } from "next-intl";

/** The Access & permissions page frame: the section's heading and what it is for, then its content. */
export function PermissionsShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("permissions");

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <div className="flex items-center gap-3">
            <KeyRound className="w-6 h-6 text-primary-500" aria-hidden="true" />
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        {children}
      </div>
    </div>
  );
}
