"use client";

import { useEffect, useState, type ComponentType } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Bookmark } from "lucide-react";
import { PERIOD_KEYS, listViews, type AnalyticsView } from "@/core/analytics";
import type { Messages } from "@/lib/i18n/messages";
import { useAuth } from "@/core/auth/hooks";
import { isInstalled } from "@/core/plugins/installed";
import { usePermissionCheck } from "@/core/permissions/hooks";
import { twMerge } from "tailwind-merge";

/** One entry on the analytics rail. */
export interface AnalyticsNavView {
  /** Its label's key under `analytics.nav`, whose other keys label the rail itself. */
  key: Exclude<keyof Messages["analytics"]["nav"], "label" | "savedViews">;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /** The plugin the view reads from; the entry shows only while that plugin is installed. */
  plugin?: string;
}

/** Window event that makes the rail reload the saved views after one is saved, renamed or deleted. */
export const VIEWS_CHANGED = "analytics:views-changed";

/** Explore's route; its entry and the saved views show only to viewers with `user.read`. */
export const EXPLORE = "/dashboard/analytics/explore";

function itemClass(active: boolean) {
  return twMerge(
    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    active
      ? "bg-primary-500/15 text-primary-600 dark:text-primary-400"
      : "text-foreground hover:bg-surface-variant",
  );
}

/**
 * The analytics rail: the views it is given, then the viewer's saved Explore views. Explore and
 * the saved views show only to viewers with `user.read`, which Explore needs.
 */
export function AnalyticsNav({ views }: { views: readonly AnalyticsNavView[] }) {
  const t = useTranslations("analytics.nav");
  const pathname = usePathname()?.replace(/\/$/, "");
  const params = useSearchParams();
  const openView = params.get("view");
  // Only the period carries over; a view's own settings stay with that view.
  const period = [...params].filter(([k]) => PERIOD_KEYS.includes(k));
  const query = new URLSearchParams(period).toString();
  const { token } = useAuth();
  const canExplore = usePermissionCheck(token, "user.read") === "allowed";
  const [saved, setSaved] = useState<AnalyticsView[]>([]);
  const shown = views.filter(
    (v) => (!v.plugin || isInstalled(v.plugin)) && (v.href !== EXPLORE || canExplore),
  );

  useEffect(() => {
    if (!token || !canExplore) return;
    let active = true;
    const load = () =>
      listViews(token)
        .then((list) => {
          if (active) setSaved(list);
        })
        .catch((err: unknown) => console.error("Saved analytics views failed to load:", err));
    void load();
    window.addEventListener(VIEWS_CHANGED, load);
    return () => {
      active = false;
      window.removeEventListener(VIEWS_CHANGED, load);
    };
  }, [token, canExplore]);

  return (
    <nav aria-label={t("label")} className="lg:w-48 lg:shrink-0">
      {/* Wraps into tabs on narrow screens; a vertical rail from lg up. */}
      <ul className="flex flex-wrap gap-1 border-b border-border pb-2 lg:flex-col lg:border-b-0 lg:pb-0">
        {shown.map(({ key, href, icon: Icon }) => {
          // A view is current only on its own path, and Explore only when no saved view is open.
          const active = pathname === href && !openView;
          return (
            <li key={key}>
              <Link
                href={query ? `${href}?${query}` : href}
                aria-current={active ? "page" : undefined}
                className={itemClass(active)}
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {t(key)}
              </Link>
            </li>
          );
        })}
      </ul>
      {canExplore && saved.length > 0 && (
        <>
          <h2 className="mt-4 px-3 text-xs font-semibold uppercase text-muted-foreground">
            {t("savedViews")}
          </h2>
          <ul className="mt-1 flex flex-wrap gap-1 lg:flex-col">
            {saved.map((v) => {
              const active = pathname === EXPLORE && openView === v.id;
              const href = `${EXPLORE}?${new URLSearchParams([["view", v.id], ...period])}`;
              return (
                <li key={v.id}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={itemClass(active)}
                  >
                    <Bookmark className="w-4 h-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{v.name}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </nav>
  );
}
