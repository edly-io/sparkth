"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

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
      <Link
        href="/dashboard"
        className="mt-6 inline-block font-medium text-primary-600 hover:underline dark:text-primary-400"
      >
        {t("back")}
      </Link>
    </div>
  );
}
