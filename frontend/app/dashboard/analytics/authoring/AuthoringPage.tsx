"use client";

import { useMemo } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn } from "lucide-react";
import {
  CHAT_EVENTS,
  countSeries,
  fetchChatActivity,
  previousPeriod,
  rateSeries,
  toolTotals,
  totalOf,
  type BucketCount,
  type ChatActivityPoint,
} from "@/lib/analytics";
import { LineChart } from "@/components/ui/LineChart";
import { RankedBar } from "@/components/ui/RankedBar";
import { StatCard } from "@/components/ui/StatCard";
import { PeriodView, bothPeriods, useComparison, type PeriodData } from "../PeriodView";

const load = bothPeriods(fetchChatActivity);

export default function AuthoringPage() {
  const t = useTranslations("analytics.authoring");
  return (
    <PeriodView title={t("title")} subtitle={(range) => t("subtitle", { range })} load={load}>
      {(data) => <AuthoringContent {...data} />}
    </PeriodView>
  );
}

function AuthoringContent({ current, previous, from, to, bucket }: PeriodData<ChatActivityPoint>) {
  const t = useTranslations("analytics.authoring");
  const tTable = useTranslations("analytics.table");
  const tCompare = useTranslations("analytics.compare");
  const format = useFormatter();
  const { range, formatBucket, change } = useComparison({
    bucket,
    from,
    to,
    noPrevious: t("noPrevious"),
  });

  const { cur, prev, charts, tools } = useMemo(() => {
    // A turn with no usable AI key fails before any message is stored, so no message stands
    // for it in the rate's denominator: it counts as a failed turn but not toward the rate.
    const rated = (rows: ChatActivityPoint[]) =>
      rows.filter(
        (r) => !(r.event_type === CHAT_EVENTS.failed && r.dimension === "llm_config_unusable"),
      );
    const totals = (rows: ChatActivityPoint[]) => ({
      conversations: totalOf(rows, CHAT_EVENTS.conversations),
      messages: totalOf(rows, CHAT_EVENTS.messages),
      failed: totalOf(rows, CHAT_EVENTS.failed),
      ratedFailed: totalOf(rated(rows), CHAT_EVENTS.failed),
      attached: totalOf(rows, CHAT_EVENTS.attached),
      detached: totalOf(rows, CHAT_EVENTS.detached),
      tools: totalOf(rows, CHAT_EVENTS.tools),
    });
    const series = (rows: ChatActivityPoint[], period: { from: string; to: string }) => {
      const at = { ...period, bucket };
      const messages = countSeries(rows, CHAT_EVENTS.messages, at);
      const failed = countSeries(rows, CHAT_EVENTS.failed, at);
      return {
        messages,
        conversations: countSeries(rows, CHAT_EVENTS.conversations, at),
        failed,
        failureRate: rateSeries(countSeries(rated(rows), CHAT_EVENTS.failed, at), messages),
      };
    };
    const now = series(current, { from, to });
    const before = series(previous, previousPeriod(from, to));
    // Each chart pairs the period's series with the previous one. A longer previous period
    // (bucket floors add a slot) aligns by its end, not its start.
    const pair = (key: keyof typeof now) => ({
      series: now[key],
      comparison: before[key].slice(-now[key].length).map((d) => d.value),
    });
    return {
      cur: totals(current),
      prev: totals(previous),
      charts: {
        messages: pair("messages"),
        conversations: pair("conversations"),
        failed: pair("failed"),
        failureRate: pair("failureRate"),
      },
      tools: toolTotals(current),
    };
  }, [current, previous, from, to, bucket]);

  const percent = (n: number) => format.number(n, { style: "percent", maximumFractionDigits: 0 });

  if (Object.values(cur).every((n) => n === 0)) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
        <p className="text-muted-foreground">{t("empty")}</p>
      </div>
    );
  }

  const chart = (
    { series, comparison }: { series: BucketCount[]; comparison: number[] },
    caption: string,
    header: string,
    formatValue: (n: number) => string,
  ) => (
    <div className="bg-card rounded-xl border border-border p-6">
      <LineChart
        data={series.map((d) => ({ label: formatBucket(d.label), value: d.value }))}
        comparison={comparison}
        caption={caption}
        headers={[tTable("date"), header, tTable("previousPeriod")]}
        formatValue={formatValue}
      />
      <p className="mt-2 text-xs text-muted-foreground">{tCompare("comparisonLegend")}</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title={t("conversations")}
            value={format.number(cur.conversations)}
            hint={change(cur.conversations, prev.conversations)}
          />
          <StatCard
            title={t("messages")}
            value={format.number(cur.messages)}
            hint={change(cur.messages, prev.messages)}
          />
          <StatCard
            title={t("failedTurns")}
            value={format.number(cur.failed)}
            hint={t("failedHint", {
              // No messages has no meaningful rate, so a dash rather than Infinity% or NaN%.
              rate: cur.messages ? percent(cur.ratedFailed / cur.messages) : "—",
              change: change(cur.failed, prev.failed),
            })}
          />
          <StatCard
            title={t("documentsAttached")}
            value={format.number(cur.attached)}
            hint={t("detachedHint", {
              count: format.number(cur.detached),
              change: change(cur.attached, prev.attached),
            })}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{t("lowerBound")}</p>
      </div>
      {chart(charts.messages, t("messagesCaption", { range }), tTable("messages"), (n) =>
        format.number(n),
      )}
      {chart(
        charts.conversations,
        t("conversationsCaption", { range }),
        tTable("conversations"),
        (n) => format.number(n),
      )}
      {chart(charts.failed, t("failedTurnsCaption", { range }), tTable("failedTurns"), (n) =>
        format.number(n),
      )}
      {chart(
        charts.failureRate,
        t("failureRateCaption", { range }),
        tTable("failureRate"),
        percent,
      )}
      {tools.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-6">
          <h3 className="mb-4 text-base font-semibold text-foreground">{t("tools")}</h3>
          <RankedBar
            // A tool the frontend doesn't know shows by its raw name; a nameless one as a dash.
            data={tools.map((d) => ({ label: d.tool || "—", value: d.total, failed: d.failed }))}
            caption={t("toolsCaption", { range })}
            headers={[tTable("tool"), tTable("calls")]}
            formatValue={(n, d) =>
              d.failed
                ? t("toolValue", { total: format.number(n), failed: format.number(d.failed) })
                : format.number(n)
            }
          />
        </div>
      )}
    </div>
  );
}
