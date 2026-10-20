import { buildSeries, type Bucket, type BucketCount } from "@/lib/analytics/series";
import type { IsoDate } from "@/lib/analytics/dates";
import type { ChatActivityPoint } from "@/lib/analytics/types";

export const CHAT_EVENTS = {
  conversations: "chat.conversation_started",
  messages: "chat.message_sent",
  tools: "chat.tool_invoked",
  attached: "chat.document_attached",
  detached: "chat.document_detached",
  failed: "chat.turn_failed",
  searches: "chat.rag_search_completed",
} as const;

/** The `chat.rag_search_completed` dimension of a search that found nothing. */
export const EMPTY_SEARCH = "empty";

export function countSeries(
  rows: ChatActivityPoint[],
  eventType: string,
  range: { from: IsoDate; to: IsoDate; bucket: Bucket },
): BucketCount[] {
  const points = rows
    .filter((r) => r.event_type === eventType)
    .map((r) => ({ day: r.bucket, value: r.event_count }));
  return buildSeries(points, range);
}

export function totalOf(rows: ChatActivityPoint[], eventType: string): number {
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
  rows: ChatActivityPoint[],
): { tool: string; total: number; failed: number }[] {
  const tools = new Map<string, { tool: string; total: number; failed: number }>();
  for (const r of rows) {
    if (r.event_type !== CHAT_EVENTS.tools) continue;
    const tool = r.dimension ?? "";
    const t = tools.get(tool) ?? { tool, total: 0, failed: 0 };
    t.total += r.event_count;
    if (r.outcome === "failed") t.failed += r.event_count;
    tools.set(tool, t);
  }
  return [...tools.values()];
}
