"use client";

import type { ReactNode } from "react";
import { Spinner } from "@/core/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";

/** The shell every settings page shares: heading, loading state, load error, then the page's content. */
export function SettingsPage({
  title,
  subtitle,
  loading,
  loadingLabel,
  error,
  actions,
  children,
}: {
  title: string;
  subtitle: string;
  loading: boolean;
  loadingLabel: string;
  error?: string | null;
  actions?: ReactNode;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="text-center">
          <Spinner className="mx-auto mb-4" />
          <p className="text-muted-foreground">{loadingLabel}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="border-b border-border px-6 py-4">
        <h1 className="text-xl font-semibold text-foreground">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <div className="px-4 py-4 sm:py-6 sm:px-6 lg:px-8">
        {error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <>
            {actions && <div className="mb-4 sm:mb-6">{actions}</div>}
            {children}
          </>
        )}
      </div>
    </div>
  );
}

/** A card of settings rows, or the `empty` content when there are none. */
export function SettingsList({ empty, children }: { empty: ReactNode; children: ReactNode[] }) {
  if (children.length === 0) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        {empty}
      </div>
    );
  }
  return (
    <div role="list" className="bg-card rounded-lg shadow-sm overflow-hidden border border-border">
      {children}
    </div>
  );
}
