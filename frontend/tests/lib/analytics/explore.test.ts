import { describe, it, expect } from "vitest";

import {
  exploreParams,
  isFilterValueValid,
  parseExploreConfig,
  pruneConfig,
  type EventCatalogEntry,
  type ExploreConfig,
} from "@/lib/analytics";

const config: ExploreConfig = {
  event: "compose.tool_invoked",
  actor: "42",
  filters: [
    { field: "outcome", value: "failed" },
    { field: "outcome", value: "null" },
    { field: "detail", value: "a:b" },
  ],
  measure: "distinct_actors",
  groupBy: "actor",
  chart: "table",
};

const catalog: EventCatalogEntry[] = [
  {
    event_type: "compose.tool_invoked",
    fields: [
      { name: "outcome", kind: "enum", values: ["ok", "failed"], nullable: true },
      { name: "detail", kind: "string", values: null, nullable: false },
      { name: "tool", kind: "string", values: null, nullable: false },
      { name: "attempts", kind: "integer", values: null, nullable: false },
      { name: "retried", kind: "boolean", values: null, nullable: false },
    ],
  },
];

describe("parseExploreConfig / exploreParams", () => {
  it("round-trips a config through the URL", () => {
    expect(parseExploreConfig(exploreParams(config))).toEqual(config);
  });

  it("omits defaults from the URL", () => {
    const params = exploreParams({
      event: "x",
      actor: null,
      filters: [],
      measure: "count",
      groupBy: null,
      chart: "line",
    });
    expect(params.toString()).toBe("event=x");
  });

  it("falls back to count and line for unknown measure and chart", () => {
    const parsed = parseExploreConfig(new URLSearchParams("measure=sum&chart=pie"));
    expect(parsed.measure).toBe("count");
    expect(parsed.chart).toBe("line");
    expect(parsed.event).toBeNull();
  });
});

describe("pruneConfig", () => {
  it("drops an event that is no longer in the catalog, with its filters and grouping", () => {
    const stale = { ...config, event: "gone.event", groupBy: "outcome" };
    expect(pruneConfig(stale, catalog)).toEqual({
      config: { ...stale, event: null, filters: [], groupBy: null },
      dropped: true,
    });
  });

  it("drops an unknown filter field and an unknown grouping", () => {
    const stale = {
      ...config,
      filters: [...config.filters, { field: "removed", value: "x" }],
      groupBy: "removed",
    };
    expect(pruneConfig(stale, catalog)).toEqual({
      config: { ...stale, filters: config.filters, groupBy: null },
      dropped: true,
    });
  });

  it("drops filter values the field no longer accepts", () => {
    const stale = {
      ...config,
      filters: [
        ...config.filters,
        { field: "outcome", value: "removed_reason" },
        { field: "attempts", value: "two" },
        { field: "retried", value: "yes" },
      ],
    };
    expect(pruneConfig(stale, catalog)).toEqual({ config, dropped: true });
  });

  it("keeps null, integer and free-text filter values", () => {
    const valid = {
      ...config,
      filters: [
        { field: "tool", value: "null" },
        { field: "attempts", value: "-3" },
        { field: "retried", value: "false" },
        { field: "detail", value: "anything" },
      ],
    };
    expect(pruneConfig(valid, catalog)).toEqual({ config: valid, dropped: false });
  });

  it("keeps grouping by actor", () => {
    expect(pruneConfig(config, catalog)).toEqual({ config, dropped: false });
  });

  it("leaves a valid config untouched", () => {
    const valid = { ...config, groupBy: "tool" };
    expect(pruneConfig(valid, catalog)).toEqual({ config: valid, dropped: false });
  });
});

describe("isFilterValueValid", () => {
  const attempts = { name: "attempts", kind: "integer" as const, values: null, nullable: false };

  it("accepts integers within int32 only", () => {
    expect(isFilterValueValid(attempts, "2147483647")).toBe(true);
    expect(isFilterValueValid(attempts, "-2147483648")).toBe(true);
    expect(isFilterValueValid(attempts, "2147483648")).toBe(false);
    expect(isFilterValueValid(attempts, "99999999999")).toBe(false);
  });
});
