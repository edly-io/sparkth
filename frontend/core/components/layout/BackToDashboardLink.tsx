"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

/** A link back to the dashboard, for a page panel that has nothing else to offer. */
export function BackToDashboardLink(): React.JSX.Element {
  const t = useTranslations("dashboardLink");

  return (
    <Link
      href="/dashboard"
      className="font-medium text-primary-600 hover:underline dark:text-primary-400"
    >
      {t("back")}
    </Link>
  );
}
