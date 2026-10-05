import { addDays, daysInclusive, parseIsoDate, type IsoDate } from "@/lib/analytics/dates";
import type { Bucket } from "@/lib/analytics/series";

export const PRESETS = { "7d": 7, "30d": 30, "90d": 90, "12m": 365 } as const;
export type Preset = keyof typeof PRESETS;
export const DEFAULT_PRESET: Preset = "30d";
export const BUCKETS: readonly Bucket[] = ["day", "week", "month"];
// The read API's `days` ceiling. It counts back from today, so this bounds how far back a
// range may start (not its length) until the API takes explicit ranges.
export const MAX_RANGE_DAYS = 365;

export interface Period {
  from: IsoDate;
  to: IsoDate;
  bucket: Bucket;
  preset: Preset | null; // null for a custom range
}

export type RangeError = "invalidDate" | "startAfterEnd" | "inFuture" | "tooFarBack";

const isPreset = (v: string | null): v is Preset => v !== null && Object.hasOwn(PRESETS, v);
const isBucket = (v: string | null): v is Bucket =>
  v !== null && (BUCKETS as readonly string[]).includes(v);

export function presetPeriod(preset: Preset, bucket: Bucket, today: IsoDate): Period {
  return { from: addDays(today, -(PRESETS[preset] - 1)), to: today, bucket, preset };
}

export function validateRange(from: string, to: string, today: IsoDate): RangeError | null {
  if (!parseIsoDate(from) || !parseIsoDate(to)) return "invalidDate";
  if (from > to) return "startAfterEnd";
  if (to > today) return "inFuture";
  if (daysInclusive(from, today) > MAX_RANGE_DAYS) return "tooFarBack";
  return null;
}

// Reads a period from URL params. An invalid custom range falls back to the default preset
// and reports why, so a bad shared link still renders.
export function parsePeriod(
  params: { get(name: string): string | null },
  today: IsoDate,
): { period: Period; error: RangeError | null } {
  const b = params.get("bucket");
  const bucket: Bucket = isBucket(b) ? b : "day";
  const from = params.get("from");
  const to = params.get("to");
  if (from !== null || to !== null) {
    const error = validateRange(from ?? "", to ?? "", today);
    if (error === null) return { period: { from: from!, to: to!, bucket, preset: null }, error };
    return { period: presetPeriod(DEFAULT_PRESET, bucket, today), error };
  }
  const range = params.get("range");
  return {
    period: presetPeriod(isPreset(range) ? range : DEFAULT_PRESET, bucket, today),
    error: null,
  };
}

export function periodQuery(period: Period): string {
  const params = new URLSearchParams(
    period.preset ? { range: period.preset } : { from: period.from, to: period.to },
  );
  params.set("bucket", period.bucket);
  return params.toString();
}
