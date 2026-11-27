"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert } from "@/lib/components/ui/Alert";
import { Button } from "@/lib/components/ui/Button";
import { NotFound } from "@/lib/components/layout/NotFound";
import { Spinner } from "@/lib/components/ui/Spinner";
import { ApiRequestError, isNotFoundError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/hooks";
import { usePermissionCheck } from "@/lib/permissions/hooks";
import { getActivityLaunch, type LaunchPermission } from "@/plugins/pxc/src/client";
import { RetryAlert } from "@/plugins/pxc/src/components/ui/RetryAlert";

const ACTIVITIES_PATH = "/dashboard/pxc";

type LaunchError = "notFound" | "forbidden" | "notConfigured" | "failed";

// A 403 means the user may not open this view and a 503 means the server has no launch secret;
// a retry fixes neither.
function launchErrorOf(error: unknown): LaunchError {
  if (isNotFoundError(error)) return "notFound";
  if (error instanceof ApiRequestError && error.status === 403) return "forbidden";
  return error instanceof ApiRequestError && error.status === 503 ? "notConfigured" : "failed";
}

function PermissionToggle({
  value,
  canEdit,
  onChange,
}: {
  value: LaunchPermission;
  canEdit: boolean;
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
      {canEdit && (
        <Button
          size="sm"
          variant={value === "edit" ? "primary" : "ghost"}
          aria-pressed={value === "edit"}
          onClick={() => onChange("edit")}
        >
          {t("authorView")}
        </Button>
      )}
    </div>
  );
}

// One launch of the activity, reporting the activity's owner once it resolves. The parent keys it
// by permission and attempt, so a toggle or a retry mounts a fresh launch.
function LaunchFrame({
  activityId,
  permission,
  onOwner,
  onRetry,
}: {
  activityId: string;
  permission: LaunchPermission;
  onOwner: (ownerId: number) => void;
  onRetry: () => void;
}): React.JSX.Element {
  const { token } = useAuth();
  const t = useTranslations("pxc");
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [error, setError] = useState<LaunchError | null>(null);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    getActivityLaunch(token, activityId, permission, controller.signal)
      .then((launch) => {
        setEmbedUrl(launch.embed_url);
        onOwner(launch.owner_user_id);
      })
      .catch((launchError: unknown) => {
        if (controller.signal.aborted) return;
        console.error(`pxc: failed to launch activity ${activityId}`, launchError);
        setError(launchErrorOf(launchError));
      });
    return () => controller.abort();
  }, [token, activityId, permission, onOwner]);

  if (error === "notFound")
    return <NotFound title={t("notFound")} message={t("notFoundMessage")} />;
  if (error === "forbidden") return <Alert severity="error">{t("notPermitted")}</Alert>;
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

// The preview's URL. The Author view is kept in it, so a reload stays in that view.
function previewPath(activityId: string, permission: LaunchPermission): string {
  const query = new URLSearchParams({ activity: activityId });
  if (permission === "edit") query.set("as", "edit");
  return `${ACTIVITIES_PATH}?${query}`;
}

// One activity iframed under the permission from the URL; the parent keys it by activity id. The
// Author button shows once a launch has named the owner and the user may edit their activities.
export function ActivityPreview({
  activityId,
  permission,
}: {
  activityId: string;
  permission: LaunchPermission;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  const router = useRouter();
  const { token } = useAuth();
  const [attempt, setAttempt] = useState(0);
  const [ownerId, setOwnerId] = useState<number | null>(null);
  const mayEdit = usePermissionCheck(ownerId === null ? null : token, "pxc.activity.edit", {
    scope: "user",
    scopeObjectId: ownerId === null ? undefined : String(ownerId),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-4">
        <Link href={ACTIVITIES_PATH} className="text-sm text-primary-600 hover:underline">
          {t("backToList")}
        </Link>
        <PermissionToggle
          value={permission}
          canEdit={mayEdit === "allowed"}
          onChange={(next) => router.replace(previewPath(activityId, next))}
        />
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <LaunchFrame
          key={`${permission}:${attempt}`}
          activityId={activityId}
          permission={permission}
          onOwner={setOwnerId}
          onRetry={() => setAttempt((count) => count + 1)}
        />
      </div>
    </div>
  );
}
