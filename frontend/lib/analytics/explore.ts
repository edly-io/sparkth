import type { EventCatalogEntry } from "@/lib/analytics/types";

/** What an Explore chart counts: events, or distinct actors. */
export type Measure = "count" | "distinct_actors";
/** How an Explore result is drawn. */
export type ChartKind = "line" | "bar" | "table";

/**
 * An Explore view's settings, as kept in the URL and in a saved view. `groupBy` is a field name
 * or `"actor"`.
 */
export type ExploreConfig = {
  event: string | null;
  actor: string | null;
  filters: { field: string; value: string }[];
  measure: Measure;
  groupBy: string | null;
  chart: ChartKind;
};

type EventField = EventCatalogEntry["fields"][number];

/** The values a filter on `field` picks from (`null` included when nullable); null for free text. */
export function filterChoices(field: EventField): string[] | null {
  const base =
    field.kind === "enum"
      ? (field.values ?? [])
      : field.kind === "boolean"
        ? ["true", "false"]
        : null;
  return base && (field.nullable ? [...base, "null"] : base);
}

/**
 * Whether the API accepts `value` as a filter on `field`; `null` matches null or missing on any
 * field. Integers must fit int32.
 */
export function isFilterValueValid(field: EventField, value: string): boolean {
  if (value === "null") return true;
  const choices = filterChoices(field);
  if (choices) return choices.includes(value);
  if (field.kind !== "integer") return value !== "";
  const n = Number(value);
  return /^-?\d+$/.test(value) && n >= -(2 ** 31) && n < 2 ** 31;
}

/** Reads an Explore config from URL params; unknown values fall back to the defaults. */
export function parseExploreConfig(params: {
  get(name: string): string | null;
  getAll(name: string): string[];
}): ExploreConfig {
  const measure = params.get("measure");
  const chart = params.get("chart");
  return {
    event: params.get("event") || null,
    actor: params.get("actor") || null,
    // The first `:` splits field from value, so a value may itself contain `:`.
    filters: params.getAll("filter").flatMap((f) => {
      const i = f.indexOf(":");
      return i > 0 ? [{ field: f.slice(0, i), value: f.slice(i + 1) }] : [];
    }),
    measure: measure === "distinct_actors" ? measure : "count",
    groupBy: params.get("group") || null,
    chart: chart === "bar" || chart === "table" ? chart : "line",
  };
}

/** The URL params of an Explore config, leaving out defaults. */
export function exploreParams(config: ExploreConfig): URLSearchParams {
  const params = new URLSearchParams();
  if (config.event) params.set("event", config.event);
  if (config.actor) params.set("actor", config.actor);
  for (const f of config.filters) params.append("filter", `${f.field}:${f.value}`);
  if (config.measure !== "count") params.set("measure", config.measure);
  if (config.groupBy) params.set("group", config.groupBy);
  if (config.chart !== "line") params.set("chart", config.chart);
  return params;
}

/**
 * Drops the parts of a config the catalog no longer has: an unknown event (with its filters
 * and grouping), filters on unknown fields or with values the field no longer accepts, and an
 * unknown or integer grouping. `dropped` says whether anything was removed.
 */
export function pruneConfig(
  config: ExploreConfig,
  catalog: EventCatalogEntry[],
): { config: ExploreConfig; dropped: boolean } {
  const entry = catalog.find((e) => e.event_type === config.event);
  if (!entry) {
    return {
      config: { ...config, event: null, filters: [], groupBy: null },
      dropped: config.event !== null,
    };
  }
  const fields = new Map(entry.fields.map((f) => [f.name, f]));
  const filters = config.filters.filter((f) => {
    const field = fields.get(f.field);
    return field !== undefined && isFilterValueValid(field, f.value);
  });
  const group = config.groupBy && fields.get(config.groupBy);
  const groupBy =
    config.groupBy === "actor" || (group && group.kind !== "integer") ? config.groupBy : null;
  const dropped = filters.length !== config.filters.length || groupBy !== config.groupBy;
  return { config: dropped ? { ...config, filters, groupBy } : config, dropped };
}
