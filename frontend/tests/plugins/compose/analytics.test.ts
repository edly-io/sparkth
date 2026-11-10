import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiRequestError } from "@/lib/api";
import {
  COMPOSE_EVENTS,
  countSeries,
  fetchComposeActivity,
  rateSeries,
  toolTotals,
  totalOf,
  type ComposeActivityPoint,
} from "@/plugins/compose/analytics";

import { mockFetch, sentRequest } from "@/tests/lib/test-utils";

// authMiddleware reads the stored token; stub it to null so the explicit bearer
// header from the client is what we assert on.
vi.mock("@/core/auth/tokens", () => ({
  getStoredToken: vi.fn().mockReturnValue(null),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

const row = (
  bucket: string,
  event_type: string,
  event_count: number,
  dimension?: string | null,
  outcome?: string | null,
): ComposeActivityPoint => ({ bucket, event_type, event_count, dimension, outcome });

const rows = [
  row("2026-07-01", COMPOSE_EVENTS.messages, 4),
  row("2026-07-03", COMPOSE_EVENTS.messages, 2),
  row("2026-07-03", COMPOSE_EVENTS.failed, 1, "timeout"),
  row("2026-07-01", COMPOSE_EVENTS.tools, 3, "search", "succeeded"),
  row("2026-07-01", COMPOSE_EVENTS.tools, 1, "search", "failed"),
  row("2026-07-02", COMPOSE_EVENTS.tools, 2, "search"),
  row("2026-07-02", COMPOSE_EVENTS.tools, 5, "outline", null),
];
const range = { from: "2026-07-01", to: "2026-07-03", bucket: "day" } as const;

describe("countSeries", () => {
  it("zero-fills the range and ignores other event types", () => {
    expect(countSeries(rows, COMPOSE_EVENTS.messages, range)).toEqual([
      { label: "2026-07-01", value: 4 },
      { label: "2026-07-02", value: 0 },
      { label: "2026-07-03", value: 2 },
    ]);
  });
});

describe("totalOf", () => {
  it("sums one event type", () => {
    expect(totalOf(rows, COMPOSE_EVENTS.messages)).toBe(6);
    expect(totalOf(rows, COMPOSE_EVENTS.detached)).toBe(0);
  });
});

describe("rateSeries", () => {
  it("divides failed by messages and is 0 where there are no messages", () => {
    const failed = countSeries(rows, COMPOSE_EVENTS.failed, range);
    const messages = countSeries(rows, COMPOSE_EVENTS.messages, range);
    expect(rateSeries(failed, messages)).toEqual([
      { label: "2026-07-01", value: 0 },
      { label: "2026-07-02", value: 0 },
      { label: "2026-07-03", value: 0.5 },
    ]);
  });
});

describe("toolTotals", () => {
  it("splits failed and counts a missing outcome in the total only", () => {
    expect(toolTotals(rows)).toEqual([
      { tool: "search", total: 6, failed: 1 },
      { tool: "outline", total: 5, failed: 0 },
    ]);
  });
});

describe("fetchComposeActivity", () => {
  it("GETs /api/v1/compose/analytics/activity for a day range with the bearer token", async () => {
    const points = [
      {
        bucket: "2026-07-20",
        event_type: "compose.tool_invoked",
        dimension: "search",
        outcome: null,
        event_count: 2,
      },
    ];
    const spy = mockFetch(points);

    const result = await fetchComposeActivity("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    });

    const url = new URL(sentRequest(spy).url);
    expect(url.pathname).toBe("/api/v1/compose/analytics/activity");
    expect(url.searchParams.get("from")).toBe("2026-07-01");
    expect(url.searchParams.get("to")).toBe("2026-07-20");
    expect(url.searchParams.get("bucket")).toBe("day");
    expect(sentRequest(spy).headers.get("authorization")).toBe("Bearer test-token");
    expect(result).toEqual(points);
  });

  it("propagates an ApiRequestError with its status intact", async () => {
    mockFetch({ detail: "Permission denied" }, 403);

    const error = await fetchComposeActivity("test-token", {
      from: "2026-07-01",
      to: "2026-07-20",
    }).catch((e: unknown) => e);

    expect((error as ApiRequestError).status).toBe(403);
  });
});
