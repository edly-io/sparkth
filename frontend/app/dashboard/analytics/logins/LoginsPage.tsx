"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  addDays,
  buildSeries,
  daysInclusive,
  fetchLogins,
  summarize,
  type Bucket,
  type IsoDate,
  type LoginsPoint,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { LineChart } from "@/components/ui/LineChart";
import { RankedBar } from "@/components/ui/RankedBar";
import { StatCard } from "@/components/ui/StatCard";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Forbidden } from "@/components/Forbidden";
import { Spinner } from "@/components/Spinner";
import type { Messages } from "@/lib/i18n/messages";
import { usePeriod } from "../usePeriod";

type LabelledMethod = keyof Messages["analytics"]["logins"]["methods"];

type State =
  | { status: "loading" }
  | {
      status: "ready";
      current: LoginsPoint[];
      previous: LoginsPoint[];
      from: IsoDate;
      to: IsoDate;
    }
  | { status: "forbidden" }
  | { status: "error" };

// API days are UTC calendar days; format them in UTC or a user west of UTC sees the day before.
const utc = (day: string) => new Date(`${day}T00:00:00Z`);

// The equally long period that ends the day before `from`.
function previousPeriod(from: IsoDate, to: IsoDate): { from: IsoDate; to: IsoDate } {
  const n = daysInclusive(from, to);
  return { from: addDays(from, -n), to: addDays(from, -1) };
}

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
    const { from, to } = period;
    setState({ status: "loading" });
    Promise.all([fetchLogins(token, { from, to }), fetchLogins(token, previousPeriod(from, to))])
      .then(([current, previous]) => {
        if (active) setState({ status: "ready", current, previous, from, to });
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
    // Only the bucket reshapes the loaded rows, so changing it doesn't refetch.
  }, [token, period.from, period.to, reloadKey]);

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
          current={state.current}
          previous={state.previous}
          from={state.from}
          to={state.to}
          bucket={period.bucket}
        />
      )}
    </div>
  );
}

function AnalyticsContent({
  current,
  previous,
  from,
  to,
  bucket,
}: {
  current: LoginsPoint[];
  previous: LoginsPoint[];
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
  const { series, total, busiest, prevSeries, prevTotal, prevBusiest, methods } = useMemo(() => {
    // Rows are per method; buildSeries adds rows sharing a bucket, so methods sum per bucket.
    const toSeries = (rows: LoginsPoint[], range: { from: IsoDate; to: IsoDate }) =>
      buildSeries(
        rows.map((p) => ({ day: p.bucket, value: p.login_count })),
        { ...range, bucket },
      );
    const series = toSeries(current, { from, to });
    const prevSeries = toSeries(previous, previousPeriod(from, to));
    const prev = summarize(prevSeries);
    const methods = new Map<string, number>();
    for (const p of current) methods.set(p.method, (methods.get(p.method) ?? 0) + p.login_count);
    return {
      series,
      ...summarize(series),
      prevSeries,
      prevTotal: prev.total,
      prevBusiest: prev.busiest,
      methods,
    };
  }, [current, previous, from, to, bucket]);

  // Zero before has no meaningful percentage, so say so rather than show Infinity%.
  const change = (cur: number, prev: number) =>
    prev === 0
      ? t("noPrevious")
      : t("vsPrevious", {
          change: format.number(cur / prev - 1, {
            style: "percent",
            signDisplay: "exceptZero",
            maximumFractionDigits: 0,
          }),
        });
  // A method added server-side before the frontend has a label shows by its raw name. The
  // cast only types the key for `t`; `t.has` is what checks it exists.
  const methodLabel = (m: string) => {
    const key = `methods.${m}` as `methods.${LabelledMethod}`;
    return t.has(key) ? t(key) : m;
  };

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
        <StatCard
          title={t("totalLogins")}
          value={format.number(total)}
          hint={change(total, prevTotal)}
        />
        <StatCard
          title={t("busiestBucket", { bucket })}
          value={busiest ? format.number(busiest.value) : "—"}
          hint={
            busiest
              ? `${formatBucket(busiest.label)} · ${change(busiest.value, prevBusiest?.value ?? 0)}`
              : undefined
          }
        />
      </div>
      <div className="bg-card rounded-xl border border-border p-6">
        <LineChart
          data={series.map((d) => ({ label: formatBucket(d.label), value: d.value }))}
          // A longer previous period (bucket floors add a slot) aligns by its end, not its start.
          comparison={prevSeries.slice(-series.length).map((d) => d.value)}
          caption={t("chartCaption", { range })}
          headers={[tTable("date"), tTable("logins"), tTable("previousPeriod")]}
          formatValue={(n) => format.number(n)}
        />
        <p className="mt-2 text-xs text-muted-foreground">{t("comparisonLegend")}</p>
      </div>
      <div className="bg-card rounded-xl border border-border p-6">
        <h3 className="mb-4 text-base font-semibold text-foreground">{t("byMethod")}</h3>
        <RankedBar
          data={[...methods].map(([m, value]) => ({ label: methodLabel(m), value }))}
          caption={t("methodChartCaption", { range })}
          headers={[tTable("method"), tTable("logins")]}
          formatValue={(n) =>
            t("methodValue", {
              count: format.number(n),
              share: format.number(n / total, { style: "percent", maximumFractionDigits: 0 }),
            })
          }
        />
      </div>
    </div>
  );
}
