"use client";

import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { BackToDashboardLink } from "@/core/components/layout/BackToDashboardLink";
import { MessagePanel } from "@/core/components/layout/MessagePanel";

// Rendered in place of content the user lacks permission for. It names no permission, so
// nothing about the access model is disclosed. A static export can't send a 403 status, so
// this is the client-side equivalent.
export function Forbidden() {
  const t = useTranslations("forbidden");

  return (
    <MessagePanel
      icon={ShieldAlert}
      title={t("title")}
      message={t("message")}
      action={<BackToDashboardLink />}
    />
  );
}
