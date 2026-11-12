// UTC calendar-date helpers over ISO `YYYY-MM-DD` strings. Analytics buckets are UTC
// server-side, so nothing here reads local time. ISO dates compare correctly as strings.
export type IsoDate = string;

const DAY_MS = 86_400_000;

export function toIsoDate(d: Date): IsoDate {
  return d.toISOString().slice(0, 10);
}

export function parseIsoDate(s: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(`${s}T00:00:00Z`);
  // Date rolls 2026-02-30 over to March; a round-trip mismatch means the day doesn't exist.
  return Number.isNaN(d.getTime()) || toIsoDate(d) !== s ? null : d;
}

export function addDays(day: IsoDate, n: number): IsoDate {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return toIsoDate(d);
}

export function daysInclusive(from: IsoDate, to: IsoDate): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS) + 1;
}
