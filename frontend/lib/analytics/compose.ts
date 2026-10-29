import { buildSeries, type Bucket, type BucketCount } from "@/lib/analytics/series";
import type { IsoDate } from "@/lib/analytics/dates";
import type { ComposeActivityPoint } from "@/lib/analytics/types";

export const COMPOSE_EVENTS = {
  conversations: "compose.conversation_started",
  messages: "compose.message_sent",
  tools: "compose.tool_invoked",
  attached: "compose.document_attached",
  detached: "compose.document_detached",
  failed: "compose.turn_failed",
  searches: "compose.rag_search_completed",
} as const;

/** The `compose.rag_search_completed` dimension of a search that found nothing. */
export const EMPTY_SEARCH = "empty";

export function countSeries(
  rows: ComposeActivityPoint[],
  eventType: string,
  range: { from: IsoDate; to: IsoDate; bucket: Bucket },
): BucketCount[] {
  const points = rows
    .filter((r) => r.event_type === eventType)
    .map((r) => ({ day: r.bucket, value: r.event_count }));
  return buildSeries(points, range);
}

export function totalOf(rows: ComposeActivityPoint[], eventType: string): number {
  return rows.reduce((sum, r) => (r.event_type === eventType ? sum + r.event_count : sum), 0);
}

/**
 * Failed turns per message sent, bucket by bucket. A bucket with no messages has no meaningful
 * rate, so it is 0 rather than NaN or Infinity.
 */
export function rateSeries(failed: BucketCount[], messages: BucketCount[]): BucketCount[] {
  return failed.map(({ label, value }, i) => ({
    label,
    value: messages[i]?.value ? value / messages[i].value : 0,
  }));
}

/**
 * Calls and failed calls per tool, in first-seen order. A call with no recorded outcome counts in
 * `total` only.
 */
export function toolTotals(
  rows: ComposeActivityPoint[],
): { tool: string; total: number; failed: number }[] {
  const tools = new Map<string, { tool: string; total: number; failed: number }>();
  for (const r of rows) {
    if (r.event_type !== COMPOSE_EVENTS.tools) continue;
    const tool = r.dimension ?? "";
    const t = tools.get(tool) ?? { tool, total: 0, failed: 0 };
    t.total += r.event_count;
    if (r.outcome === "failed") t.failed += r.event_count;
    tools.set(tool, t);
  }
  return [...tools.values()];
}
