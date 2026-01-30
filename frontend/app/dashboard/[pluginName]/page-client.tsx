"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { usePlugin } from "@/lib/plugins/context";
import { getPlugin } from "@/lib/plugins";
import PluginRenderer from "@/components/PluginRenderer";
import Link from "next/link";

export default function PluginPageClient() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();

  const pluginName = params?.pluginName as string;

  const { isEnabled } = usePlugin(pluginName);
  const pluginDef = getPlugin(pluginName);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push(`/login?redirect=/dashboard/${pluginName}`);
    }
  }, [authLoading, isAuthenticated, router, pluginName]);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-muted-foreground">Authenticating...</p>
        </div>
      </div>
    );
  }

  if (!pluginName) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center max-w-md">
          <div className="text-error-600 dark:text-error-400 mb-4">
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
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Invalid URL
          </h2>
          <p className="text-muted-foreground mb-4">
            No plugin name specified.
          </p>
          <Link
            className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            href="/dashboard"
          >
            Go to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!pluginDef) {
    return (
      <div className="flex items-center justify-center h-full min-h-screen bg-background">
        <div className="text-center max-w-md">
          <div className="text-muted mb-4">
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
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Plugin Not Found
          </h2>
          <p className="text-muted-foreground mb-4">
            No plugin registered with name:{" "}
            <code className="bg-surface-variant px-2 py-1 rounded text-foreground">
              {pluginName}
            </code>
          </p>
          <Link
            className="inline-block px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            href="/dashboard"
          >
            Go to Dashboard
          </Link>
        </div>
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
          <h2 className="text-2xl font-bold text-foreground mb-2">
            Plugin Not Enabled
          </h2>
          <p className="text-muted-foreground mb-4">
            {pluginDef.displayName} is not enabled for your account.
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
