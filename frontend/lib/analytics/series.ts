import type { LoginActivityPoint } from "@/lib/analytics/types";
import { addDays, parseIsoDate, toIsoDate, type IsoDate } from "@/lib/analytics/dates";

export interface BucketCount {
  label: string;
  value: number;
}

export function buildDailySeries(
  points: LoginActivityPoint[],
  days: number,
  now: Date,
): BucketCount[] {
  const to = toIsoDate(now);
  return buildSeries(
    points.map((p) => ({ day: p.day, value: p.login_count })),
    { from: addDays(to, 1 - days), to, bucket: "day" },
  );
}

export function summarize(series: BucketCount[]): {
  total: number;
  busiest: BucketCount | null;
} {
  const total = series.reduce((sum, d) => sum + d.value, 0);
  const busiest = series.reduce<BucketCount | null>(
    (best, d) => (!best || d.value > best.value ? d : best),
    null,
  );
  return { total, busiest };
}

export type Bucket = "day" | "week" | "month";

// The first day of the bucket containing `day`, which must be a valid date. Weeks start on
// Monday (ISO 8601).
export function bucketStart(day: IsoDate, bucket: Bucket): IsoDate {
  if (bucket === "day") return day;
  if (bucket === "month") return `${day.slice(0, 7)}-01`;
  const weekday = new Date(`${day}T00:00:00Z`).getUTCDay(); // 0 = Sunday
  return addDays(day, -((weekday + 6) % 7));
}

function advance(d: Date, bucket: Bucket): void {
  if (bucket === "month") d.setUTCMonth(d.getUTCMonth() + 1);
  else d.setUTCDate(d.getUTCDate() + (bucket === "week" ? 7 : 1));
}

export function buildSeries(
  points: { day: IsoDate; value: number }[],
  { from, to, bucket }: { from: IsoDate; to: IsoDate; bucket: Bucket },
): BucketCount[] {
  const start = parseIsoDate(from);
  const end = parseIsoDate(to);
  if (!start || !end || start > end) return [];

  const totals = new Map<IsoDate, number>();
  for (const d = parseIsoDate(bucketStart(from, bucket))!; d <= end; advance(d, bucket)) {
    totals.set(toIsoDate(d), 0);
  }
  for (const p of points) {
    if (!parseIsoDate(p.day) || p.day < from || p.day > to) continue;
    const key = bucketStart(p.day, bucket);
    totals.set(key, (totals.get(key) ?? 0) + p.value);
  }
  return [...totals].map(([label, value]) => ({ label, value }));
}
