import type { LoginActivityPoint } from "@/lib/analytics/types";

// A single point in a login-activity series: a day label and its count. Kept
// structurally identical to the chart's `BarChartDatum` so a series can be
// passed straight to <BarChart> without the data layer importing a UI type.
export interface DailyCount {
  label: string;
  value: number;
}

// The API omits zero-login days (newest-first, sparse). Build a continuous
// oldest→newest series of `days` UTC days, filling missing days with 0. `now`
// is injectable so the derivation is unit-testable without faking the clock.
export function buildDailySeries(
  points: LoginActivityPoint[],
  days: number,
  now: Date,
): DailyCount[] {
  const counts = new Map(points.map((p) => [p.day, p.login_count]));
  const series: DailyCount[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10); // YYYY-MM-DD (UTC), matches API `day`
    series.push({ label: key, value: counts.get(key) ?? 0 });
  }
  return series;
}

export function summarize(series: DailyCount[]): {
  total: number;
  busiest: DailyCount | null;
} {
  const total = series.reduce((sum, d) => sum + d.value, 0);
  const busiest = series.reduce<DailyCount | null>(
    (best, d) => (!best || d.value > best.value ? d : best),
    null,
  );
  return { total, busiest };
}
