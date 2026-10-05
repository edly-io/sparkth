import { describe, it, expect } from "vitest";

import { buildSeries, bucketStart, summarize } from "@/lib/analytics";

describe("summarize", () => {
  it("derives total logins and the busiest day from a windowed series", () => {
    const series = [
      { label: "2026-07-21", value: 2 },
      { label: "2026-07-22", value: 0 },
      { label: "2026-07-23", value: 5 },
    ];

    const { total, busiest } = summarize(series);

    expect(total).toBe(7);
    expect(busiest).toEqual({ label: "2026-07-23", value: 5 });
  });

  it("returns zero total and null busiest for an empty series", () => {
    expect(summarize([])).toEqual({ total: 0, busiest: null });
  });
});

describe("bucketStart", () => {
  it("starts weeks on Monday, across a year boundary", () => {
    expect(bucketStart("2026-01-01", "week")).toBe("2025-12-29"); // Thu → Mon
    expect(bucketStart("2025-12-29", "week")).toBe("2025-12-29"); // Mon stays
    expect(bucketStart("2026-01-04", "week")).toBe("2025-12-29"); // Sun → previous Mon
  });

  it("starts months on the 1st", () => {
    expect(bucketStart("2026-07-15", "month")).toBe("2026-07-01");
  });
});

describe("buildSeries", () => {
  const points = [
    { day: "2026-01-02", value: 3 },
    { day: "2025-12-30", value: 2 },
    { day: "2025-12-01", value: 9 }, // before `from`: ignored
  ];

  it("zero-fills each day oldest→newest", () => {
    expect(buildSeries(points, { from: "2025-12-30", to: "2026-01-02", bucket: "day" })).toEqual([
      { label: "2025-12-30", value: 2 },
      { label: "2025-12-31", value: 0 },
      { label: "2026-01-01", value: 0 },
      { label: "2026-01-02", value: 3 },
    ]);
  });

  it("sums into Monday-start weeks, labelling a partial first week by its Monday", () => {
    expect(buildSeries(points, { from: "2025-12-30", to: "2026-01-05", bucket: "week" })).toEqual([
      { label: "2025-12-29", value: 5 },
      { label: "2026-01-05", value: 0 },
    ]);
  });

  it("sums into calendar months across a year boundary", () => {
    expect(buildSeries(points, { from: "2025-12-15", to: "2026-01-31", bucket: "month" })).toEqual([
      { label: "2025-12-01", value: 2 },
      { label: "2026-01-01", value: 3 },
    ]);
  });

  it("returns a single zero bucket for a one-day range with no data", () => {
    expect(buildSeries([], { from: "2026-07-01", to: "2026-07-01", bucket: "day" })).toEqual([
      { label: "2026-07-01", value: 0 },
    ]);
  });

  it("includes a partial trailing week, labelled by its Monday", () => {
    expect(buildSeries([], { from: "2026-01-05", to: "2026-01-14", bucket: "week" })).toEqual([
      { label: "2026-01-05", value: 0 },
      { label: "2026-01-12", value: 0 },
    ]);
  });

  it("steps one bucket at a time over a long range", () => {
    const series = buildSeries([], { from: "1900-01-01", to: "2026-12-31", bucket: "month" });
    expect(series).toHaveLength((2026 - 1900 + 1) * 12);
    expect(series[0].label).toBe("1900-01-01");
    expect(series.at(-1)?.label).toBe("2026-12-01");
  });

  it("returns an empty series for a malformed or inverted range", () => {
    expect(buildSeries([], { from: "2026-2-3", to: "2026-03-01", bucket: "day" })).toEqual([]);
    expect(buildSeries([], { from: "2026-03-01", to: "2026-02-30", bucket: "month" })).toEqual([]);
    expect(buildSeries([], { from: "2026-03-02", to: "2026-03-01", bucket: "day" })).toEqual([]);
  });

  it("drops points whose day is malformed instead of throwing or inventing a bucket", () => {
    const bad = [
      { day: "2026-2-3", value: 5 },
      { day: "not-a-date", value: 5 },
      { day: "2026-03-02", value: 1 },
    ];
    expect(buildSeries(bad, { from: "2026-03-01", to: "2026-03-31", bucket: "month" })).toEqual([
      { label: "2026-03-01", value: 1 },
    ]);
    expect(buildSeries(bad, { from: "2026-03-02", to: "2026-03-02", bucket: "week" })).toEqual([
      { label: "2026-03-02", value: 1 },
    ]);
  });

  it("stops at the last representable date instead of looping past year 9999", () => {
    expect(buildSeries([], { from: "9999-12-30", to: "9999-12-31", bucket: "day" })).toEqual([
      { label: "9999-12-30", value: 0 },
      { label: "9999-12-31", value: 0 },
    ]);
    expect(buildSeries([], { from: "9999-12-01", to: "9999-12-31", bucket: "month" })).toEqual([
      { label: "9999-12-01", value: 0 },
    ]);
  });
});
