"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  buildSeries,
  daysInclusive,
  fetchLoginActivity,
  summarize,
  toIsoDate,
  type Bucket,
  type IsoDate,
  type LoginActivityPoint,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { BarChart } from "@/components/ui/BarChart";
import { StatCard } from "@/components/ui/StatCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Forbidden } from "@/components/Forbidden";
import { Spinner } from "@/components/Spinner";
import { usePeriod } from "../usePeriod";

type State =
  | { status: "loading" }
  | { status: "ready"; points: LoginActivityPoint[]; from: IsoDate }
  | { status: "forbidden" }
  | { status: "error" };

// API days are UTC calendar days; format them in UTC or a user west of UTC sees the day before.
const utc = (day: string) => new Date(`${day}T00:00:00Z`);

export default function LoginsPage() {
  const { token } = useAuth();
  const t = useTranslations("analytics");
  const format = useFormatter();
  const { period } = usePeriod();
  const [state, setState] = useState<State>({ status: "loading" });

  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (!token) return;
    let active = true;
    const { from } = period;
    setState({ status: "loading" });
    // The API only counts back from today, so ask for enough days to reach `from`.
    fetchLoginActivity(token, { days: daysInclusive(from, toIsoDate(new Date())) })
      .then((points) => {
        if (active) setState({ status: "ready", points, from });
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
    // `to` and the bucket only reshape the loaded points, so changing them doesn't refetch.
  }, [token, period.from, reloadKey]);

  const retry = useCallback(() => setReloadKey((key) => key + 1), []);

  // Access revoked after the layout's check: the read API answered 403.
  if (state.status === "forbidden") {
    return <Forbidden />;
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-foreground">{t("logins.title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("logins.subtitle", {
            range: format.dateTimeRange(utc(period.from), utc(period.to), {
              dateStyle: "medium",
              timeZone: "UTC",
            }),
          })}
        </p>
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
        <AnalyticsContent
          points={state.points}
          from={state.from}
          to={period.to}
          bucket={period.bucket}
        />
      )}
    </div>
  );
}

function AnalyticsContent({
  points,
  from,
  to,
  bucket,
}: {
  points: LoginActivityPoint[];
  from: IsoDate;
  to: IsoDate;
  bucket: Bucket;
}) {
  const t = useTranslations("analytics.logins");
  const tTable = useTranslations("analytics.table");
  const format = useFormatter();
  // A bucket label is its first day: a week reads "Week of <Monday>", a month its month name.
  const formatBucket = (day: string) => {
    if (bucket === "month") {
      return format.dateTime(utc(day), { month: "short", year: "numeric", timeZone: "UTC" });
    }
    const date = format.dateTime(utc(day), { dateStyle: "medium", timeZone: "UTC" });
    return bucket === "week" ? t("weekOf", { date }) : date;
  };
  const range = format.dateTimeRange(utc(from), utc(to), { dateStyle: "medium", timeZone: "UTC" });
  const { series, total, busiest } = useMemo(() => {
    const series = buildSeries(
      points.map((p) => ({ day: p.day, value: p.login_count })),
      { from, to, bucket },
    );
    return { series, ...summarize(series) };
  }, [points, from, to, bucket]);

  if (total === 0) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
        <p className="text-muted-foreground">{t("empty")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <StatCard title={t("totalLogins")} value={format.number(total)} hint={range} />
        <StatCard
          title={t("busiestBucket", { bucket })}
          value={busiest ? format.number(busiest.value) : "—"}
          hint={busiest ? formatBucket(busiest.label) : undefined}
        />
      </div>
      <div className="bg-card rounded-xl border border-border p-6">
        <BarChart
          data={series.map((d) => ({ label: formatBucket(d.label), value: d.value }))}
          caption={t("chartCaption", { range })}
          headers={[tTable("date"), tTable("logins")]}
          formatValue={(n) => format.number(n)}
        />
      </div>
    </div>
  );
}
