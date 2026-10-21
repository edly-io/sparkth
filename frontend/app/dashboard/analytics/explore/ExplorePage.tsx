"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { ChartColumn, X } from "lucide-react";
import {
  PERIOD_KEYS,
  buildSeries,
  exploreParams,
  fetchEventCatalog,
  fetchExplore,
  filterChoices,
  isFilterValueValid,
  parseExploreConfig,
  pruneConfig,
  type ChartKind,
  type EventCatalogEntry,
  type ExploreConfig,
  type ExploreResult,
  type Measure,
} from "@/lib/analytics";
import { ApiRequestError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Alert } from "@/components/ui/Alert";
import { BarChart } from "@/components/ui/BarChart";
import { Button } from "@/components/ui/Button";
import { ChartTable } from "@/components/ui/ChartTable";
import { Input } from "@/components/ui/Input";
import { LineChart } from "@/components/ui/LineChart";
import { RankedBar } from "@/components/ui/RankedBar";
import { Select } from "@/components/ui/Select";
import { Forbidden } from "@/components/Forbidden";
import { Spinner } from "@/components/Spinner";
import { PeriodView, useComparison, type PeriodRange } from "../PeriodView";
import { usePeriod } from "../usePeriod";

const MEASURES: Measure[] = ["count", "distinct_actors"];
const CHARTS: ChartKind[] = ["line", "bar", "table"];
const VISIBLE_TABLE =
  "w-full text-left text-sm [&_caption]:mb-2 [&_caption]:text-left [&_td]:py-1 [&_th]:py-1";

/**
 * Builds a chart from any recorded event: pick an event, filter, measure, break down and chart
 * type. The settings live in the URL, so a configured view can be bookmarked or shared. Event
 * types, field names and values show as recorded.
 */
export default function ExplorePage() {
  const t = useTranslations("analytics.explore");
  const tAnalytics = useTranslations("analytics");
  const { token } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { period } = usePeriod();
  const [catalog, setCatalog] = useState<EventCatalogEntry[] | "forbidden" | "error" | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    fetchEventCatalog(token)
      .then((entries) => {
        if (active) setCatalog(entries);
      })
      .catch((err: unknown) => {
        console.error("Analytics event catalog failed to load:", err);
        if (active) {
          setCatalog(err instanceof ApiRequestError && err.status === 403 ? "forbidden" : "error");
        }
      });
    return () => {
      active = false;
    };
  }, [token]);

  const query = params.toString();
  const pruned = useMemo(
    () =>
      Array.isArray(catalog)
        ? pruneConfig(parseExploreConfig(new URLSearchParams(query)), catalog)
        : null,
    [query, catalog],
  );
  // The last query written but not yet in the URL: router.replace lands after a commit, so a
  // second change made before then must build on the first, not on the rendered config.
  const pending = useRef<string | null>(null);
  useEffect(() => {
    pending.current = null;
  }, [query]);

  if (catalog === "forbidden") return <Forbidden />;
  if (catalog === "error") return <Alert severity="error">{tAnalytics("loadError")}</Alert>;
  if (!pruned || !Array.isArray(catalog)) {
    return (
      <div className="flex justify-center py-24">
        <Spinner />
      </div>
    );
  }

  const { config, dropped } = pruned;
  // Keeps the period, replaces Explore's own settings.
  const update = (change: (current: ExploreConfig) => ExploreConfig) => {
    const latest = new URLSearchParams(pending.current ?? query);
    const current = pruneConfig(parseExploreConfig(latest), catalog).config;
    const kept = [...latest].filter(([k]) => PERIOD_KEYS.includes(k));
    const q = new URLSearchParams([...kept, ...exploreParams(change(current))]).toString();
    if (q === latest.toString()) return;
    pending.current = q;
    router.replace(q ? `${pathname}?${q}` : pathname);
  };
  const entry = catalog.find((e) => e.event_type === config.event);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-foreground">{t("title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("description")}</p>
      </div>
      {dropped && <Alert severity="warning">{t("stale")}</Alert>}
      {/* Keyed by event, so a half-built filter doesn't outlive its event's fields. */}
      <Controls
        key={config.event ?? ""}
        catalog={catalog}
        entry={entry}
        config={config}
        update={update}
      />
      {config.event ? (
        <PeriodView
          // A new config or bucket is a new query.
          key={`${exploreParams(config)}&bucket=${period.bucket}`}
          title={config.event}
          subtitle={(range) => t("subtitle", { range })}
          load={(tok, range) => fetchExplore(tok, { ...range, bucket: period.bucket }, config)}
        >
          {(data) => <Results {...data} config={config} />}
        </PeriodView>
      ) : (
        <Empty text={t("start")} />
      )}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="bg-card rounded-lg shadow-sm p-12 text-center border border-border">
      <ChartColumn className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
      <p className="text-muted-foreground">{text}</p>
    </div>
  );
}

function Controls({
  catalog,
  entry,
  config,
  update,
}: {
  catalog: EventCatalogEntry[];
  entry: EventCatalogEntry | undefined;
  config: ExploreConfig;
  update: (change: (current: ExploreConfig) => ExploreConfig) => void;
}) {
  const t = useTranslations("analytics.explore");
  const [fieldName, setFieldName] = useState("");
  const [value, setValue] = useState("");
  const fields = entry?.fields ?? [];
  const field = fields.find((f) => f.name === fieldName);
  const options = field ? filterChoices(field) : null;

  const pickField = (name: string) => {
    const picked = fields.find((f) => f.name === name);
    setFieldName(name);
    setValue((picked && filterChoices(picked)?.[0]) ?? "");
  };
  const addFilter = () => {
    update((c) => ({ ...c, filters: [...c.filters, { field: fieldName, value }] }));
    setFieldName("");
    setValue("");
  };
  const commitActor = (raw: string) => {
    update((c) => ({ ...c, actor: raw.trim() || null }));
  };

  return (
    <div className="bg-card rounded-xl border border-border p-6 space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Select
          id="explore-event"
          label={t("event")}
          placeholder={t("pickEvent")}
          value={config.event ?? ""}
          options={catalog.map((e) => ({ value: e.event_type, label: e.event_type }))}
          // A different event has different fields, so its filters and breakdown go.
          onChange={(e) =>
            update((c) => ({ ...c, event: e.target.value, filters: [], groupBy: null }))
          }
        />
        <Input
          id="explore-actor"
          // Remounts when the URL's actor changes, so the box shows it.
          key={config.actor ?? ""}
          label={t("actorId")}
          defaultValue={config.actor ?? ""}
          onBlur={(e) => commitActor(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && commitActor(e.currentTarget.value)}
        />
        <Select
          id="explore-measure"
          label={t("measure")}
          value={config.measure}
          options={MEASURES.map((m) => ({ value: m, label: t(`measures.${m}`) }))}
          onChange={(e) => update((c) => ({ ...c, measure: e.target.value as Measure }))}
        />
        <Select
          id="explore-group"
          label={t("groupBy")}
          value={config.groupBy ?? ""}
          options={[
            { value: "", label: t("noGroup") },
            { value: "actor", label: t("actor") },
            ...fields
              .filter((f) => f.kind !== "integer")
              .map((f) => ({ value: f.name, label: f.name })),
          ]}
          onChange={(e) => update((c) => ({ ...c, groupBy: e.target.value || null }))}
        />
        <Select
          id="explore-chart"
          label={t("chart")}
          value={config.chart}
          options={CHARTS.map((c) => ({ value: c, label: t(`charts.${c}`) }))}
          onChange={(e) => update((c) => ({ ...c, chart: e.target.value as ChartKind }))}
        />
      </div>

      {entry && (
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-foreground">{t("filters")}</legend>
          {config.filters.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {config.filters.map((f, i) => (
                <li
                  key={i}
                  className="flex items-center gap-1 rounded-full bg-surface-variant px-3 py-1 text-sm"
                >
                  <span>{`${f.field} = ${f.value}`}</span>
                  <button
                    type="button"
                    aria-label={t("removeFilter", { filter: `${f.field} = ${f.value}` })}
                    onClick={() =>
                      update((c) => ({ ...c, filters: c.filters.filter((_, j) => j !== i) }))
                    }
                  >
                    <X className="w-3 h-3" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="grid grid-cols-1 items-end gap-4 sm:grid-cols-[1fr_1fr_auto]">
            <Select
              id="explore-filter-field"
              label={t("field")}
              placeholder={t("pickField")}
              value={fieldName}
              options={fields.map((f) => ({ value: f.name, label: f.name }))}
              onChange={(e) => pickField(e.target.value)}
            />
            {options ? (
              <Select
                id="explore-filter-value"
                label={t("value")}
                value={value}
                options={options.map((v) => ({ value: v, label: v }))}
                onChange={(e) => setValue(e.target.value)}
              />
            ) : (
              <Input
                id="explore-filter-value"
                label={t("value")}
                value={value}
                disabled={!field}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
            <Button
              variant="secondary"
              disabled={!field || !isFilterValueValid(field, value)}
              onClick={addFilter}
            >
              {t("addFilter")}
            </Button>
          </div>
        </fieldset>
      )}
    </div>
  );
}

function Results({
  config,
  points,
  totals,
  truncated,
  actor_names,
  from,
  to,
  bucket,
}: ExploreResult & PeriodRange & { config: ExploreConfig }) {
  const t = useTranslations("analytics.explore");
  const tTable = useTranslations("analytics.table");
  const format = useFormatter();
  const { range, formatBucket } = useComparison({ bucket, from, to, noPrevious: "" });
  const formatValue = (n: number) => format.number(n);
  const measure = t(`measures.${config.measure}`);
  const event = config.event ?? "";

  if (config.groupBy) {
    if (totals.length === 0) return <Empty text={t("empty")} />;
    const isActor = config.groupBy === "actor";
    const group = isActor ? t("actor") : config.groupBy;
    const data = totals.map((d) => ({
      label: d.group === null ? t("none") : isActor ? (actor_names[d.group] ?? d.group) : d.group,
      value: d.value,
    }));
    const caption = t("groupCaption", { event, group, range });
    return (
      <div className="bg-card rounded-xl border border-border p-6 space-y-4">
        {config.chart === "table" ? (
          <ChartTable
            className={VISIBLE_TABLE}
            caption={caption}
            headers={[group, measure]}
            rows={data.map((d) => [d.label, formatValue(d.value)])}
          />
        ) : (
          <RankedBar
            data={data}
            limit={20}
            caption={caption}
            headers={[group, measure]}
            formatValue={formatValue}
          />
        )}
        {truncated && <p className="text-xs text-muted-foreground">{t("truncated")}</p>}
      </div>
    );
  }

  const series = buildSeries(
    points.map((p) => ({ day: p.bucket, value: p.value })),
    { from, to, bucket },
  ).map((d) => ({ label: formatBucket(d.label), value: d.value }));
  if (!series.some((d) => d.value)) return <Empty text={t("empty")} />;
  const caption = t("chartCaption", { event, range });
  const headers: [string, string] = [tTable("date"), measure];
  return (
    <div className="bg-card rounded-xl border border-border p-6">
      {config.chart === "line" && (
        <LineChart data={series} caption={caption} headers={headers} formatValue={formatValue} />
      )}
      {config.chart === "bar" && (
        <BarChart data={series} caption={caption} headers={headers} formatValue={formatValue} />
      )}
      {config.chart === "table" && (
        <ChartTable
          className={VISIBLE_TABLE}
          caption={caption}
          headers={headers}
          rows={series.map((d) => [d.label, formatValue(d.value)])}
        />
      )}
    </div>
  );
}
