"use client";

import { useParams, redirect } from "next/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/core/auth/hooks";
import { Spinner } from "@/core/components/ui/Spinner";
import { usePlugin, usePluginContext } from "@/core/plugins/context";
import { displayNameOf } from "@/core/plugins/metadata";
import { pluginPath } from "@/core/plugins/routes";
import PluginRenderer from "@/core/plugins/components/layout/PluginRenderer";
import Link from "next/link";

function PluginUnavailable({
  title,
  message,
  showSettingsLink,
}: {
  title: string;
  message: string;
  showSettingsLink: boolean;
}) {
  const tPage = useTranslations("pluginPage");

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
        <h2 className="text-2xl font-bold text-foreground mb-2">{title}</h2>
        <p className="text-muted-foreground mb-4">{message}</p>
        <div className="flex justify-center gap-3">
          {showSettingsLink && (
            <Link
              className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
              href="/dashboard/settings/"
            >
              {tPage("enableInSettings")}
            </Link>
          )}

          <Link
            className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            href="/dashboard"
          >
            {tPage("goBack")}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function PluginPageClient() {
  const params = useParams();
  const tPage = useTranslations("pluginPage");
  const { isAuthenticated, loading: authLoading } = useAuth();

  const pluginName = String(params?.pluginName ?? "");

  const { isEnabled } = usePlugin(pluginName);
  const { plugins, loading: pluginsLoading } = usePluginContext();

  const plugin = plugins.find((p) => p.plugin_name === pluginName);
  const displayName = plugin ? displayNameOf(plugin) : pluginName;

  if (!authLoading && !isAuthenticated) {
    redirect(`/login?redirect=${pluginPath(pluginName)}`);
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">{tPage("authenticating")}</p>
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

  if (plugin && !plugin.system_enabled) {
    return (
      <PluginUnavailable
        title={tPage("systemDisabledTitle")}
        message={tPage("systemDisabledMessage", { name: displayName })}
        showSettingsLink={false}
      />
    );
  }

  if (!isEnabled) {
    return (
      <PluginUnavailable
        title={tPage("notEnabledTitle")}
        message={tPage("notEnabledMessage", { name: displayName })}
        showSettingsLink
      />
    );
  }

  return (
    <div className="h-full bg-background">
      <PluginRenderer pluginName={pluginName} />
    </div>
  );
}
