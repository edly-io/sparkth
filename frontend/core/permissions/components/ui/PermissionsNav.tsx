"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { twMerge } from "tailwind-merge";
import type { Messages } from "@/lib/i18n/messages";

/** One tab of the Access & permissions section. */
export interface PermissionsTab {
  /** Its label's key under `permissions.nav`, whose `label` key names the tab bar itself. */
  key: Exclude<keyof Messages["permissions"]["nav"], "label">;
  href: string;
}

/**
 * The Access & permissions tab bar: a link per tab, the open one marked as the current page. A tab
 * is open on its own path and on any path below it.
 */
export function PermissionsNav({ tabs }: { tabs: readonly PermissionsTab[] }) {
  const t = useTranslations("permissions.nav");
  const pathname = usePathname()?.replace(/\/$/, "") ?? "";

  return (
    <nav aria-label={t("label")} className="mb-6 overflow-x-auto border-b border-border">
      <ul className="flex gap-1">
        {tabs.map(({ key, href }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={key}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={twMerge(
                  "-mb-px block whitespace-nowrap border-b-2 px-4 py-3 text-sm transition-colors",
                  active
                    ? "border-primary-500 font-semibold text-primary-600 dark:text-primary-400"
                    : "border-transparent font-medium text-muted-foreground hover:text-foreground",
                )}
              >
                {t(key)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
