"use client";

import { useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import { BackToDashboardLink } from "@/core/components/layout/BackToDashboardLink";
import { NotFound } from "@/core/components/layout/NotFound";

// The address does not change while this page shows, so there is nothing to subscribe to.
function unsubscribeFromNothing(): void {}

function subscribeToNothing(): () => void {
  return unsubscribeFromNothing;
}

function getPathname(): string {
  return window.location.pathname;
}

// One exported file answers every unknown address, so it is built without knowing any of them.
function getUnknownPathname(): null {
  return null;
}

// A plugin's page lives at the single segment after /dashboard.
function getPluginNameOrNull(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  return segments.length === 2 && segments[0] === "dashboard" ? segments[1] : null;
}

/**
 * The page for an address that names no page.
 *
 * An address where a plugin's page would live says no plugin has that name; any other address
 * says the page was not found. Both lead back to the dashboard. Nothing shows until the browser's
 * address is known.
 */
export default function NotFoundPage(): React.JSX.Element | null {
  const tPage = useTranslations("pageNotFound");
  const tPlugin = useTranslations("pluginNotFound");
  const pathname = useSyncExternalStore(subscribeToNothing, getPathname, getUnknownPathname);
  if (pathname === null) return null;

  const pluginName = getPluginNameOrNull(pathname);
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <NotFound
          title={pluginName ? tPlugin("title") : tPage("title")}
          message={pluginName ? tPlugin("message", { name: pluginName }) : tPage("message")}
          action={<BackToDashboardLink />}
        />
      </div>
    </div>
  );
}
