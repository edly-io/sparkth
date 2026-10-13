"use client";

import { useMemo } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn } from "lucide-react";
import {
  buildSeries,
  fetchLogins,
  previousPeriod,
  summarize,
  type IsoDate,
  type LoginsPoint,
} from "@/lib/analytics";
import { LineChart } from "@/components/ui/LineChart";
import { RankedBar } from "@/components/ui/RankedBar";
import { StatCard } from "@/components/ui/StatCard";
import type { Messages } from "@/lib/i18n/messages";
import { PeriodView, useComparison, type PeriodData } from "../PeriodView";

type LabelledMethod = keyof Messages["analytics"]["logins"]["methods"];

export default function LoginsPage() {
  const t = useTranslations("analytics.logins");
  return (
    <PeriodView
      title={t("title")}
      subtitle={(range) => t("subtitle", { range })}
      fetcher={fetchLogins}
    >
      {(data) => <AnalyticsContent {...data} />}
    </PeriodView>
  );
}

function AnalyticsContent({ current, previous, from, to, bucket }: PeriodData<LoginsPoint>) {
  const t = useTranslations("analytics.logins");
  const tTable = useTranslations("analytics.table");
  const format = useFormatter();
  const tCompare = useTranslations("analytics.compare");
  const { range, formatBucket, change } = useComparison({
    bucket,
    from,
    to,
    noPrevious: t("noPrevious"),
  });
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
        <p className="mt-2 text-xs text-muted-foreground">{tCompare("comparisonLegend")}</p>
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
