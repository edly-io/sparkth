import type { DriveDocumentsPoint } from "@/lib/analytics/types";

/**
 * Documents processed, how many became ready (by the server's `ready` flag), their average
 * seconds to ready (null when none did), and the not-ready outcomes by count, largest first.
 */
export function documentTotals(rows: DriveDocumentsPoint[]) {
  let total = 0;
  let ready = 0;
  let readySeconds = 0;
  const notReady = new Map<string, number>();
  for (const r of rows) {
    total += r.document_count;
    if (r.ready) {
      ready += r.document_count;
      readySeconds += r.seconds_total;
    } else {
      const key = r.outcome ?? "";
      notReady.set(key, (notReady.get(key) ?? 0) + r.document_count);
    }
  }
  return {
    total,
    ready,
    avgSecondsToReady: ready ? Math.round(readySeconds / ready) : null,
    notReady: [...notReady]
      .map(([outcome, count]) => ({ outcome, count }))
      .sort((a, b) => b.count - a.count),
  };
}
