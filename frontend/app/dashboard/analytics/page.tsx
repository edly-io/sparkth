"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn } from "lucide-react";
import {
  CHAT_EVENTS,
  buildSeries,
  countSeries,
  fetchChatActivity,
  fetchLogins,
  fetchSummary,
  previousPeriod,
  type BucketCount,
  type ChatActivityPoint,
  type IsoDate,
  type LoginsPoint,
  type SummaryCount,
} from "@/lib/analytics";
import { LineChart } from "@/components/ui/LineChart";
import { StatCard } from "@/components/ui/StatCard";
import { isInstalled } from "@/lib/plugins";
import { ANALYTICS_VIEWS } from "./AnalyticsNav";
import { PeriodView, useComparison, type PeriodRange } from "./PeriodView";

/** Everything the Overview loads for the period and the one before it. */
type OverviewData = {
  figures: SummaryCount[];
  logins: LoginsPoint[];
  prevLogins: LoginsPoint[];
  activity: ChatActivityPoint[];
  prevActivity: ChatActivityPoint[];
};

/** The analytics index: one card per headline figure the server declares, for the selected period. */
export default function OverviewPage() {
  const t = useTranslations("analytics.overview");
  const chat = isInstalled("chat");
  const load = async (token: string, range: { from: IsoDate; to: IsoDate }) => {
    const prev = previousPeriod(range.from, range.to);
    const [figures, logins, prevLogins, activity, prevActivity] = await Promise.all([
      fetchSummary(token, range),
      fetchLogins(token, range),
      fetchLogins(token, prev),
      chat ? fetchChatActivity(token, range) : [],
      chat ? fetchChatActivity(token, prev) : [],
    ]);
    return { figures, logins, prevLogins, activity, prevActivity };
  };
  return (
    <PeriodView title={t("title")} subtitle={(range) => t("subtitle", { range })} load={load}>
      {(data) => <OverviewCards {...data} />}
    </PeriodView>
  );
}

/** Draws one card per figure, linked to the view that breaks it down, then the activity trend. */
function OverviewCards({ figures, from, to, bucket, ...rest }: OverviewData & PeriodRange) {
  const t = useTranslations("analytics.overview");
  const format = useFormatter();
  const query = useSearchParams().toString();
  const { change } = useComparison({ bucket, from, to, noPrevious: t("new") });

  if (figures.every((f) => f.current === 0 && f.previous === 0)) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
        <p className="text-muted-foreground">{t("empty")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {figures.map((f) => {
          const card = (
            <StatCard
              title={f.label}
              value={format.number(f.current)}
              hint={f.current || f.previous ? change(f.current, f.previous) : undefined}
              className="h-full"
            />
          );
          const view = ANALYTICS_VIEWS.find((v) => v.key === f.view);
          return view ? (
            <Link
              key={f.key}
              href={query ? `${view.href}?${query}` : view.href}
              className="block rounded-xl transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
            >
              {card}
            </Link>
          ) : (
            <div key={f.key}>{card}</div>
          );
        })}
      </div>
      <OverviewTrend {...rest} from={from} to={to} bucket={bucket} />
    </div>
  );
}

/** One period's rows the activity trend reads. */
type TrendRows = { logins: LoginsPoint[]; activity: ChatActivityPoint[] };

/** One activity source's count per bucket, on the bucket grid of `opts`. */
type TrendSource = (rows: TrendRows, opts: PeriodRange) => BucketCount[];

const loginsSeries: TrendSource = ({ logins }, opts) =>
  buildSeries(
    logins.map((p) => ({ day: p.bucket, value: p.login_count })),
    opts,
  );

const messagesSeries: TrendSource = ({ activity }, opts) =>
  countSeries(activity, CHAT_EVENTS.messages, opts);

/** The sources the activity trend adds up; a new source is one more entry here. */
const TREND_SOURCES: TrendSource[] = [loginsSeries, messagesSeries];

/** Every source's count, summed bucket by bucket. All series share the same grid. */
function activitySeries(rows: TrendRows, opts: PeriodRange): BucketCount[] {
  const [first, ...others] = TREND_SOURCES.map((source) => source(rows, opts));
  return first.map((d, i) => ({
    ...d,
    value: others.reduce((sum, s) => sum + (s[i]?.value ?? 0), d.value),
  }));
}

/** Logins plus messages sent per bucket, against the previous period. */
function OverviewTrend({
  logins,
  prevLogins,
  activity,
  prevActivity,
  from,
  to,
  bucket,
}: Omit<OverviewData, "figures"> & PeriodRange) {
  const t = useTranslations("analytics.overview");
  const tTable = useTranslations("analytics.table");
  const tCompare = useTranslations("analytics.compare");
  const format = useFormatter();
  const { range, formatBucket } = useComparison({
    bucket,
    from,
    to,
    noPrevious: "",
  });
  const series = activitySeries({ logins, activity }, { from, to, bucket });
  const prev = activitySeries(
    { logins: prevLogins, activity: prevActivity },
    { ...previousPeriod(from, to), bucket },
  );
  return (
    <div className="bg-card rounded-xl border border-border p-6">
      <h3 className="mb-4 text-base font-semibold text-foreground">{t("trend")}</h3>
      <LineChart
        data={series.map((d) => ({
          label: formatBucket(d.label),
          value: d.value,
        }))}
        comparison={prev.slice(-series.length).map((d) => d.value)}
        caption={t("trendCaption", { range })}
        headers={[tTable("date"), tTable("activity"), tTable("previousPeriod")]}
        formatValue={(n) => format.number(n)}
      />
      <p className="mt-2 text-xs text-muted-foreground">{tCompare("comparisonLegend")}</p>
    </div>
  );
}
