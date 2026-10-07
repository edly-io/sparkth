"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/Spinner";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { getActivityEmbedUrl, type LaunchPermission } from "@/plugins/pxc/client";
import { RetryAlert } from "@/plugins/pxc/components/RetryAlert";

const ACTIVITIES_PATH = "/dashboard/pxc";

type LaunchError = "notFound" | "failed";

interface LaunchView {
  permission: LaunchPermission;
  embedUrl: string | null;
  error: LaunchError | null;
}

function freshView(permission: LaunchPermission): LaunchView {
  return { permission, embedUrl: null, error: null };
}

// A malformed id fails path validation (422), which for the author is a missing activity too.
function launchErrorOf(error: unknown): LaunchError {
  return error instanceof ApiRequestError && (error.status === 404 || error.status === 422)
    ? "notFound"
    : "failed";
}

function PermissionToggle({
  value,
  onChange,
}: {
  value: LaunchPermission;
  onChange: (permission: LaunchPermission) => void;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  return (
    <div role="group" aria-label={t("viewAs")} className="flex gap-2">
      <Button
        size="sm"
        variant={value === "play" ? "primary" : "ghost"}
        aria-pressed={value === "play"}
        onClick={() => onChange("play")}
      >
        {t("studentView")}
      </Button>
      <Button
        size="sm"
        variant={value === "edit" ? "primary" : "ghost"}
        aria-pressed={value === "edit"}
        onClick={() => onChange("edit")}
      >
        {t("authorView")}
      </Button>
    </div>
  );
}

function PreviewBody({
  view,
  onRetry,
}: {
  view: LaunchView;
  onRetry: () => void;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  if (view.error === "notFound") return <Alert severity="error">{t("notFound")}</Alert>;
  if (view.error === "failed") return <RetryAlert message={t("launchFailed")} onRetry={onRetry} />;
  if (view.embedUrl === null) {
    return (
      <div role="status" aria-label={t("loadingActivity")}>
        <Spinner className="mx-auto" />
      </div>
    );
  }
  // No allow-same-origin: activity code runs in an opaque origin and cannot reach Sparkth.
  return (
    <iframe
      src={view.embedUrl}
      title={t("frameTitle")}
      sandbox="allow-scripts allow-forms"
      className="h-full min-h-[600px] w-full rounded-lg border border-border bg-white"
    />
  );
}

// One activity iframed under the chosen permission; the parent keys it by activity id.
export function ActivityPreview({ activityId }: { activityId: string }): React.JSX.Element {
  const { token } = useAuth();
  const t = useTranslations("pxc");
  const [view, setView] = useState<LaunchView>(freshView("play"));
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    getActivityEmbedUrl(token, activityId, view.permission, controller.signal)
      .then((embedUrl) => {
        // A launch that lands after a toggle belongs to the old view.
        if (!controller.signal.aborted) setView((current) => ({ ...current, embedUrl }));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error(`pxc: failed to launch activity ${activityId}`, error);
        setView((current) => ({ ...current, error: launchErrorOf(error) }));
      });
    return () => controller.abort();
  }, [token, activityId, view.permission, reloadKey]);

  const retry = (): void => {
    setView((current) => freshView(current.permission));
    setReloadKey((key) => key + 1);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-4">
        <Link href={ACTIVITIES_PATH} className="text-sm text-primary-600 hover:underline">
          {t("backToList")}
        </Link>
        <PermissionToggle
          value={view.permission}
          onChange={(permission) =>
            setView((current) =>
              current.permission === permission ? current : freshView(permission),
            )
          }
        />
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <PreviewBody view={view} onRetry={retry} />
      </div>
    </div>
  );
}
