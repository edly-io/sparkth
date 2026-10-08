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

type LaunchError = "notFound" | "notConfigured" | "failed";

// A malformed id fails path validation (422), which for the author is a missing activity too.
// A 503 means the server has no launch secret, which a retry cannot fix.
function launchErrorOf(error: unknown): LaunchError {
  if (!(error instanceof ApiRequestError)) return "failed";
  if (error.status === 404 || error.status === 422) return "notFound";
  return error.status === 503 ? "notConfigured" : "failed";
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

// One launch of the activity. The parent keys it by permission and attempt, so a toggle or a
// retry mounts a fresh launch.
function LaunchFrame({
  activityId,
  permission,
  onRetry,
}: {
  activityId: string;
  permission: LaunchPermission;
  onRetry: () => void;
}): React.JSX.Element {
  const { token } = useAuth();
  const t = useTranslations("pxc");
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [error, setError] = useState<LaunchError | null>(null);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    getActivityEmbedUrl(token, activityId, permission, controller.signal)
      .then(setEmbedUrl)
      .catch((launchError: unknown) => {
        if (controller.signal.aborted) return;
        console.error(`pxc: failed to launch activity ${activityId}`, launchError);
        setError(launchErrorOf(launchError));
      });
    return () => controller.abort();
  }, [token, activityId, permission]);

  if (error === "notFound") return <Alert severity="error">{t("notFound")}</Alert>;
  if (error === "notConfigured") return <Alert severity="error">{t("notConfigured")}</Alert>;
  if (error === "failed") return <RetryAlert message={t("launchFailed")} onRetry={onRetry} />;
  if (embedUrl === null) {
    return (
      <div role="status" aria-label={t("loadingActivity")}>
        <Spinner className="mx-auto" />
      </div>
    );
  }
  // No allow-same-origin: activity code runs in an opaque origin and cannot reach Sparkth.
  return (
    <iframe
      src={embedUrl}
      title={t("frameTitle")}
      sandbox="allow-scripts allow-forms"
      className="h-full min-h-[600px] w-full rounded-lg border border-border bg-white"
    />
  );
}

// One activity iframed under the chosen permission; the parent keys it by activity id.
export function ActivityPreview({ activityId }: { activityId: string }): React.JSX.Element {
  const t = useTranslations("pxc");
  const [permission, setPermission] = useState<LaunchPermission>("play");
  const [attempt, setAttempt] = useState(0);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-4">
        <Link href={ACTIVITIES_PATH} className="text-sm text-primary-600 hover:underline">
          {t("backToList")}
        </Link>
        <PermissionToggle value={permission} onChange={setPermission} />
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <LaunchFrame
          key={`${permission}:${attempt}`}
          activityId={activityId}
          permission={permission}
          onRetry={() => setAttempt((count) => count + 1)}
        />
      </div>
    </div>
  );
}
