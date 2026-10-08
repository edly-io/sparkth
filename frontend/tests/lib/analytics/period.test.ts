import { describe, it, expect } from "vitest";
import { parsePeriod, periodQuery, presetPeriod, validateRange } from "@/lib/analytics";

const TODAY = "2026-07-24";
const q = (s: string) => new URLSearchParams(s);

describe("presetPeriod", () => {
  it("ends today and spans the preset's days inclusively", () => {
    expect(presetPeriod("7d", "day", TODAY)).toEqual({
      from: "2026-07-18",
      to: TODAY,
      bucket: "day",
      preset: "7d",
    });
    expect(presetPeriod("12m", "month", TODAY).from).toBe("2025-07-25");
  });
});

describe("validateRange", () => {
  it("accepts a valid past range", () => {
    expect(validateRange("2026-07-01", "2026-07-10", TODAY)).toBeNull();
  });
  it.each([
    ["2026-07-10", "2026-07-01", "startAfterEnd"],
    ["2026-07-01", "2026-07-25", "inFuture"],
    ["2025-07-24", "2026-07-01", "tooFarBack"], // 365 days back: outside the API's 365-day window
    ["2026-02-30", "2026-03-01", "invalidDate"],
    ["", "2026-07-01", "invalidDate"],
  ])("rejects %s → %s as %s", (from, to, error) => {
    expect(validateRange(from, to, TODAY)).toBe(error);
  });
  it("allows a start 364 days back, the oldest day the API's 365-day window covers", () => {
    expect(validateRange("2025-07-25", TODAY, TODAY)).toBeNull();
  });
});

describe("parsePeriod", () => {
  it("defaults to the last 30 days by day", () => {
    expect(parsePeriod(q(""), TODAY)).toEqual({
      period: { from: "2026-06-25", to: TODAY, bucket: "day", preset: "30d" },
      error: null,
    });
  });
  it("reads a preset and a bucket", () => {
    expect(parsePeriod(q("range=7d&bucket=week"), TODAY).period).toMatchObject({
      preset: "7d",
      bucket: "week",
    });
  });
  it("reads a custom range", () => {
    expect(parsePeriod(q("from=2026-07-01&to=2026-07-10"), TODAY).period).toEqual({
      from: "2026-07-01",
      to: "2026-07-10",
      bucket: "day",
      preset: null,
    });
  });
  it("falls back to the default and reports why for an invalid custom range", () => {
    const { period, error } = parsePeriod(q("from=2026-07-10&to=2026-07-01&bucket=month"), TODAY);
    expect(error).toBe("startAfterEnd");
    expect(period).toMatchObject({ preset: "30d", bucket: "month" });
  });
  it("ignores unknown presets and buckets, including prototype keys", () => {
    expect(parsePeriod(q("range=toString&bucket=year"), TODAY)).toEqual(parsePeriod(q(""), TODAY));
  });
});

describe("periodQuery", () => {
  it("round-trips presets and custom ranges", () => {
    for (const s of ["range=90d&bucket=week", "from=2026-07-01&to=2026-07-10&bucket=day"]) {
      const { period } = parsePeriod(q(s), TODAY);
      expect(periodQuery(period)).toBe(s);
    }
  });
});
