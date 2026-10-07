"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import { listActivities, type ActivitySummary } from "@/plugins/pxc/client";
import { RetryAlert } from "@/plugins/pxc/components/RetryAlert";

const COMPOSE_PATH = "/dashboard/chat";

function ActivityRow({ activity }: { activity: ActivitySummary }): React.JSX.Element {
  const t = useTranslations("pxc");
  const format = useFormatter();
  const created = format.dateTime(new Date(activity.created_at), { dateStyle: "medium" });
  return (
    <Card variant="outlined" className="flex items-center justify-between gap-4 p-4">
      <div className="min-w-0">
        <h3 className="font-semibold text-foreground">{activity.title}</h3>
        <p className="text-sm text-muted-foreground">{activity.description}</p>
        <p className="mt-1 text-xs text-muted">{t("createdOn", { date: created })}</p>
      </div>
      <Button asChild variant="outline" size="sm">
        <Link
          href={activity.preview_url}
          aria-label={t("previewActivity", { title: activity.title })}
        >
          {t("preview")}
        </Link>
      </Button>
    </Card>
  );
}

function EmptyState(): React.JSX.Element {
  const t = useTranslations("pxc");
  return (
    <div className="py-16 text-center">
      <h3 className="text-lg font-semibold text-foreground">{t("emptyTitle")}</h3>
      <p className="mb-4 text-sm text-muted-foreground">{t("emptyBody")}</p>
      <Button asChild size="sm">
        <Link href={COMPOSE_PATH}>{t("openCompose")}</Link>
      </Button>
    </div>
  );
}

function ActivityListBody({
  activities,
  failed,
  onRetry,
}: {
  activities: ActivitySummary[] | null;
  failed: boolean;
  onRetry: () => void;
}): React.JSX.Element {
  const t = useTranslations("pxc");
  if (failed) return <RetryAlert message={t("loadFailed")} onRetry={onRetry} />;
  if (activities === null) {
    return (
      <div role="status" aria-label={t("loading")}>
        <Spinner className="mx-auto" />
      </div>
    );
  }
  if (activities.length === 0) return <EmptyState />;
  return (
    <ul className="space-y-3">
      {activities.map((activity) => (
        <li key={activity.id}>
          <ActivityRow activity={activity} />
        </li>
      ))}
    </ul>
  );
}

// The signed-in user's activities, newest first as the backend returns them.
export function ActivityList(): React.JSX.Element {
  const { token } = useAuth();
  const t = useTranslations("pxc");
  const [activities, setActivities] = useState<ActivitySummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    listActivities(token, controller.signal)
      .then(setActivities)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        console.error("pxc: failed to list activities", error);
        setFailed(true);
      });
    return () => controller.abort();
  }, [token, reloadKey]);

  const retry = (): void => {
    setFailed(false);
    setReloadKey((key) => key + 1);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-card px-6 py-4">
        <h2 className="text-xl font-semibold text-foreground">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <ActivityListBody activities={activities} failed={failed} onRetry={retry} />
      </div>
    </div>
  );
}
