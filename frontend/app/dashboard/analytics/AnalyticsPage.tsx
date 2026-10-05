"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { redirect } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  buildDailySeries,
  fetchLoginActivity,
  LOGIN_ACTIVITY_DAYS,
  summarize,
  type LoginActivityPoint,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { BarChart } from "@/components/ui/BarChart";
import { StatCard } from "@/components/ui/StatCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/Spinner";

type State =
  | { status: "loading" }
  | { status: "ready"; points: LoginActivityPoint[]; fetchedAt: Date }
  | { status: "forbidden" }
  | { status: "error" };

export default function AnalyticsPage() {
  const { token } = useAuth();
  const t = useTranslations("analytics");
  const [state, setState] = useState<State>({ status: "loading" });

  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (!token) return;
    let active = true;
    setState({ status: "loading" });
    fetchLoginActivity(token, { days: LOGIN_ACTIVITY_DAYS })
      .then((points) => {
        if (active) setState({ status: "ready", points, fetchedAt: new Date() });
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiRequestError && err.status === 403) {
          setState({ status: "forbidden" });
        } else {
          setState({ status: "error" });
        }
      });
    return () => {
      active = false;
    };
  }, [token, reloadKey]);

  const retry = useCallback(() => setReloadKey((key) => key + 1), []);

  if (state.status === "forbidden") {
    redirect("/dashboard");
  }

  return (
    <div className="min-h-screen bg-background transition-colors">
      <div className="mx-auto px-4 py-4 sm:py-8 sm:px-6 lg:px-8">
        <div className="mb-6 sm:mb-8 flex items-center gap-3">
          <ChartColumn className="w-6 h-6 text-primary-500" />
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{t("title")}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("logins.subtitle", { days: LOGIN_ACTIVITY_DAYS })}
            </p>
          </div>
        </div>

        {state.status === "loading" && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <Spinner className="mx-auto mb-4" />
              <p className="text-muted-foreground">{t("loading")}</p>
            </div>
          </div>
        )}

        {state.status === "error" && (
          <Alert severity="error">
            <div className="flex items-center justify-between gap-3">
              <span>{t("loadError")}</span>
              <Button variant="ghost" size="sm" onClick={retry}>
                <RefreshCw className="w-4 h-4 mr-1" aria-hidden="true" />
                {t("retry")}
              </Button>
            </div>
          </Alert>
        )}

        {state.status === "ready" && (
          <AnalyticsContent points={state.points} fetchedAt={state.fetchedAt} />
        )}
      </div>
    </div>
  );
}

function AnalyticsContent({
  points,
  fetchedAt,
}: {
  points: LoginActivityPoint[];
  fetchedAt: Date;
}) {
  const t = useTranslations("analytics.logins");
  const format = useFormatter();
  // API days are UTC calendar days; format them in UTC or a user west of UTC sees the day before.
  const formatDay = (day: string) =>
    format.dateTime(new Date(`${day}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });
  const { series, total, busiest } = useMemo(() => {
    const series = buildDailySeries(points, LOGIN_ACTIVITY_DAYS, fetchedAt);
    return { series, ...summarize(series) };
  }, [points, fetchedAt]);

  if (total === 0) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
        <p className="text-muted-foreground">{t("empty", { days: LOGIN_ACTIVITY_DAYS })}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard
          title={t("totalLogins")}
          value={format.number(total)}
          hint={t("lastDays", { days: LOGIN_ACTIVITY_DAYS })}
        />
        <StatCard
          title={t("busiestDay")}
          value={busiest ? format.number(busiest.value) : "—"}
          hint={busiest ? formatDay(busiest.label) : undefined}
        />
      </div>
      <div className="bg-card rounded-xl border border-border p-6">
        <BarChart
          data={series.map((d) => ({ label: formatDay(d.label), value: d.value }))}
          aria-label={t("chartLabel", { days: LOGIN_ACTIVITY_DAYS })}
        />
      </div>
    </div>
  );
}
