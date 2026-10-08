"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { LogIn } from "lucide-react";
import { cn } from "@/lib/utils";

// The Insights-style rail: one entry per view. A view's entry lands with the view.
export const ANALYTICS_VIEWS = [
  { key: "logins", href: "/dashboard/analytics/logins", icon: LogIn },
] as const;

export function AnalyticsNav() {
  const t = useTranslations("analytics.nav");
  const pathname = usePathname();
  const query = useSearchParams().toString();

  return (
    <nav aria-label={t("label")} className="lg:w-48 lg:shrink-0">
      {/* Wraps into tabs on narrow screens; a vertical rail from lg up. */}
      <ul className="flex flex-wrap gap-1 border-b border-border pb-2 lg:flex-col lg:border-b-0 lg:pb-0">
        {ANALYTICS_VIEWS.map(({ key, href, icon: Icon }) => {
          const active = pathname === href || pathname?.startsWith(`${href}/`);
          return (
            <li key={key}>
              <Link
                href={query ? `${href}?${query}` : href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary-500/15 text-primary-600 dark:text-primary-400"
                    : "text-foreground hover:bg-surface-variant",
                )}
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {t(key)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
