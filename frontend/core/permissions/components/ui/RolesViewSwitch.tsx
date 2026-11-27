"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { ROLES_COMPARE_PATH, ROLES_PATH } from "@/core/permissions/paths";

const VIEW_CLASS = "rounded-lg px-3.5 py-2 text-sm";
const CURRENT_VIEW_CLASS = `${VIEW_CLASS} bg-card font-semibold text-foreground shadow-sm`;
const OTHER_VIEW_CLASS = `${VIEW_CLASS} font-medium text-muted-foreground`;

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
        className={
          current === "list" ? CURRENT_VIEW_CLASS : `${OTHER_VIEW_CLASS} hover:text-foreground`
        }
      >
        {t("list")}
      </Link>
      {current === "compare" ? (
        <Link href={ROLES_COMPARE_PATH} aria-current="page" className={CURRENT_VIEW_CLASS}>
          {t("compare")}
        </Link>
      ) : (
        <button
          type="button"
          disabled
          className={`${OTHER_VIEW_CLASS} disabled:cursor-not-allowed disabled:opacity-60`}
        >
          {t("compare")}
        </button>
      )}
    </div>
  );
}
