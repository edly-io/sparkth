"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn } from "lucide-react";
import { fetchSummary, type IsoDate, type SummaryCount } from "@/lib/analytics";
import { usePluginContext } from "@/lib/plugins/context";
import { StatCard } from "@/components/ui/StatCard";
import { ANALYTICS_VIEWS } from "./AnalyticsNav";
import { PeriodView, useComparison, type PeriodRange } from "./PeriodView";

/** Loads the summary; the server counts both periods in one request. */
const load = async (token: string, range: { from: IsoDate; to: IsoDate }) => ({
  figures: await fetchSummary(token, range),
});

/** The analytics index: one card per headline figure the server declares, for the selected period. */
export default function OverviewPage() {
  const t = useTranslations("analytics.overview");
  return (
    <PeriodView title={t("title")} subtitle={(range) => t("subtitle", { range })} load={load}>
      {(data) => <OverviewCards {...data} />}
    </PeriodView>
  );
}

/** Draws one card per figure and links it to the view that breaks it down. */
function OverviewCards({ figures, from, to, bucket }: { figures: SummaryCount[] } & PeriodRange) {
  const t = useTranslations("analytics.overview");
  const format = useFormatter();
  const query = useSearchParams().toString();
  const { isPluginEnabled } = usePluginContext();
  const { change } = useComparison({ bucket, from, to, noPrevious: t("new") });
  const shown = figures.filter((f) => !f.plugin || isPluginEnabled(f.plugin));

  if (shown.every((f) => f.current === 0 && f.previous === 0)) {
    return (
      <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
        <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
        <p className="text-muted-foreground">{t("empty")}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {shown.map((f) => {
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
  );
}
