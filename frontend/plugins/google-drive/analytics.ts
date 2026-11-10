/** Google Drive's analytics: its processed-documents endpoint and the totals its charts show. */

import type { IsoDate } from "@/lib/analytics";
import { api, bearer, call, type Schema } from "@/lib/api";

/**
 * One bucket's count of processed Drive documents with one outcome, whether that outcome left them
 * ready, and their summed seconds to final.
 */
export type DriveDocumentsPoint = Schema<"DriveDocumentsPoint">;

/** Processed Drive documents per day and outcome, with summed seconds to final, for the period. */
export async function fetchDriveDocuments(
  token: string,
  { from, to }: { from: IsoDate; to: IsoDate },
): Promise<DriveDocumentsPoint[]> {
  return call<DriveDocumentsPoint[]>(() =>
    api.GET("/api/v1/google-drive/analytics/documents", {
      params: { query: { from, to, bucket: "day" } },
      headers: bearer(token),
    }),
  );
}

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
