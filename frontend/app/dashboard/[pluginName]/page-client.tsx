"use client";

import { useParams, redirect } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/core/auth/hooks";
import { BackToDashboardLink } from "@/core/components/layout/BackToDashboardLink";
import { NotFound } from "@/core/components/layout/NotFound";
import { Spinner } from "@/core/components/ui/Spinner";
import { usePlugin, usePluginContext } from "@/core/plugins/context";
import { displayNameOf } from "@/core/plugins/metadata";
import { getPlugin } from "@/core/plugins/registry";
import { pluginPath } from "@/core/plugins/routes";
import PluginRenderer from "@/core/plugins/components/layout/PluginRenderer";
import Link from "next/link";

export default function PluginPageClient() {
  const params = useParams();
  const t = useTranslations("pluginNotFound");
  const { isAuthenticated, loading: authLoading } = useAuth();

  const pluginName = String(params?.pluginName ?? "");

  const { isEnabled } = usePlugin(pluginName);
  const { userPlugins, loading: pluginsLoading } = usePluginContext();
  const pluginDef = getPlugin(pluginName);

  const userPlugin = userPlugins.find((p) => p.plugin_name === pluginName);
  const displayName = userPlugin ? displayNameOf(userPlugin) : pluginName;

  if (!authLoading && !isAuthenticated) {
    redirect(`/login?redirect=${pluginPath(pluginName)}`);
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">Authenticating...</p>
        </div>
      </div>
    );
  }

  // A URL with no plugin name finds no plugin either.
  if (!pluginDef) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background p-4">
        <div className="w-full max-w-md">
          <NotFound
            title={t("title")}
            message={pluginName ? t("message", { name: pluginName }) : undefined}
            action={<BackToDashboardLink />}
          />
        </div>
      </div>
    );
  }

  // Until the plugin list loads, neither isEnabled nor displayName is
  // meaningful, so don't render a verdict yet.
  if (pluginsLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <Spinner />
      </div>
    );
  }

  if (!isEnabled) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center max-w-md">
          <div className="text-warning-500 mb-4">
            <svg
              className="w-16 h-16 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Plugin Not Enabled</h2>
          <p className="text-muted-foreground mb-4">
            {displayName} is not enabled for your account.
          </p>
          <div className="flex justify-center gap-3">
            <Link
              className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
              href="/dashboard/settings/"
            >
              Enable in Settings
            </Link>

            <Link
              className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
              href="/dashboard"
            >
              Go Back
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-background">
      <PluginRenderer pluginName={pluginName} />
    </div>
  );
}
