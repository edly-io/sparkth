"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { twMerge } from "tailwind-merge";
import { ROLES_COMPARE_PATH, ROLES_PATH } from "@/core/permissions/paths";

/** The two views of the roles, in the order the switch shows them. */
const VIEWS = [
  { key: "list", href: ROLES_PATH },
  { key: "compare", href: ROLES_COMPARE_PATH },
] as const;

/**
 * The switch between the two views of the roles, the list and the permission comparison: a link to
 * each, with `current` marked as the one on show.
 */
export function RolesViewSwitch({ current }: { current: "list" | "compare" }) {
  const t = useTranslations("permissions.roles.view");
  return (
    <div
      role="group"
      aria-label={t("label")}
      className="inline-flex rounded-[10px] bg-surface-variant p-1"
    >
      {VIEWS.map(({ key, href }) => (
        <Link
          key={key}
          href={href}
          aria-current={key === current ? "page" : undefined}
          className={twMerge(
            "rounded-lg px-3.5 py-2 text-sm font-medium text-muted-foreground",
            key === current
              ? "bg-card font-semibold text-foreground shadow-sm"
              : "hover:text-foreground",
          )}
        >
          {t(key)}
        </Link>
      ))}
    </div>
  );
}
