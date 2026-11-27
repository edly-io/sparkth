"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { twMerge } from "tailwind-merge";
import { ROLES_COMPARE_PATH, ROLES_PATH } from "@/core/permissions/paths";

/**
 * The classes of one view in the switch: the one on show, the other one, or one that cannot be
 * opened.
 */
function getViewClass(view: "current" | "other" | "unavailable"): string {
  return twMerge(
    "rounded-lg px-3.5 py-2 text-sm font-medium text-muted-foreground",
    {
      current: "bg-card font-semibold text-foreground shadow-sm",
      other: "hover:text-foreground",
      unavailable: "cursor-not-allowed opacity-60",
    }[view],
  );
}

/**
 * The switch between the two views of the roles, the list and the permission comparison, with
 * `current` marked as the one on show. The list can always be opened; from the list, the
 * comparison is shown disabled.
 */
export function RolesViewSwitch({ current }: { current: "list" | "compare" }) {
  const t = useTranslations("permissions.roles.view");
  return (
    <div
      role="group"
      aria-label={t("label")}
      className="inline-flex rounded-[10px] bg-surface-variant p-1"
    >
      <Link
        href={ROLES_PATH}
        aria-current={current === "list" ? "page" : undefined}
        className={getViewClass(current === "list" ? "current" : "other")}
      >
        {t("list")}
      </Link>
      {current === "compare" ? (
        <Link href={ROLES_COMPARE_PATH} aria-current="page" className={getViewClass("current")}>
          {t("compare")}
        </Link>
      ) : (
        <button type="button" disabled className={getViewClass("unavailable")}>
          {t("compare")}
        </button>
      )}
    </div>
  );
}
