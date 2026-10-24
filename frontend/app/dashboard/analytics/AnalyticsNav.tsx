"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Bookmark, Compass, LayoutDashboard, LogIn, PenLine } from "lucide-react";
import { PERIOD_KEYS, listViews, type AnalyticsView } from "@/lib/analytics";
import { useAuth } from "@/lib/auth-context";
import { isInstalled } from "@/lib/plugins";
import { cn } from "@/lib/utils";

// The Insights-style rail: one entry per view. A view's entry lands with the view. A view read
// from a plugin's route names that plugin, and its entry shows while that plugin is installed.
export const ANALYTICS_VIEWS = [
  { key: "overview", href: "/dashboard/analytics", icon: LayoutDashboard },
  { key: "logins", href: "/dashboard/analytics/logins", icon: LogIn },
  { key: "authoring", href: "/dashboard/analytics/authoring", icon: PenLine, plugin: "chat" },
  { key: "explore", href: "/dashboard/analytics/explore", icon: Compass },
] as const;

/** Window event that makes the rail reload the saved views after one is saved, renamed or deleted. */
export const VIEWS_CHANGED = "analytics:views-changed";

const EXPLORE = "/dashboard/analytics/explore";

function itemClass(active: boolean) {
  return cn(
    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
    active
      ? "bg-primary-500/15 text-primary-600 dark:text-primary-400"
      : "text-foreground hover:bg-surface-variant",
  );
}

/** The analytics rail: the built-in views, then the viewer's saved Explore views. */
export function AnalyticsNav() {
  const t = useTranslations("analytics.nav");
  const pathname = usePathname()?.replace(/\/$/, "");
  const params = useSearchParams();
  const openView = params.get("view");
  // Only the period carries over; a view's own settings stay with that view.
  const period = [...params].filter(([k]) => PERIOD_KEYS.includes(k));
  const query = new URLSearchParams(period).toString();
  const { token } = useAuth();
  const [saved, setSaved] = useState<AnalyticsView[]>([]);
  const views = ANALYTICS_VIEWS.filter((v) => !("plugin" in v) || isInstalled(v.plugin));

  useEffect(() => {
    if (!token) return;
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
  }, [token]);

  return (
    <nav aria-label={t("label")} className="lg:w-48 lg:shrink-0">
      {/* Wraps into tabs on narrow screens; a vertical rail from lg up. */}
      <ul className="flex flex-wrap gap-1 border-b border-border pb-2 lg:flex-col lg:border-b-0 lg:pb-0">
        {views.map(({ key, href, icon: Icon }) => {
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
      {saved.length > 0 && (
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
